import hashlib
import logging
import pprint
from typing import Final, Mapping, NamedTuple, Optional, Sequence, Type

import kubernetes
from kubernetes.client import ApiException

from .config import Service
from .crds import DefaultCRD
from .models import ConsulRouterSpec, KubernetesResource, KubernetesResourceMetadata

log: Final = logging.getLogger(__name__)

HASH_ANNOTATION: Final = "hash"
DYNAMIC_LABEL: Final = "pod-consul-sidekick"


class CRDGroup(NamedTuple):
    group: str
    version: str


class CRDResourceKind(NamedTuple):
    namespace: str
    kind: str
    plural: str


class CRDUpdater:
    _initialized = False

    def __init__(
        self,
        group: CRDGroup,
        kind: CRDResourceKind,
        name: str,
        *,
        labels: Optional[dict[str, str]] = None,
        dry_run: bool = False,
    ) -> None:
        assert self._initialized, "You need to initialize the class by calling CRDUpdater.initialize() first"

        self.group = group
        self.kind = kind
        self.name = name
        self.labels = labels
        self.dry_run = dry_run

    @classmethod
    def initialize(cls) -> None:
        try:
            kubernetes.config.load_incluster_config()
        except kubernetes.config.config_exception.ConfigException as e:
            log.warning("Unable to us incluster config; falling back to kube config: %s", e)
            kubernetes.config.load_kube_config()

        cls._initialized = True

    def _get_crd_hash(self) -> Optional[str]:
        client = kubernetes.client.CustomObjectsApi()

        try:
            result: Final = KubernetesResource.parse_obj(
                client.get_namespaced_custom_object(
                    self.group.group,
                    self.group.version,
                    self.kind.namespace,
                    self.kind.plural,
                    self.name,
                )
            )
        except ApiException as e:
            if e.status == 404:
                return None
            raise

        if result.metadata.annotations is None or HASH_ANNOTATION not in result.metadata.annotations:
            log.warning("No %s annotation for %s CRD", HASH_ANNOTATION, self.name)
            return "invalid"

        return result.metadata.annotations[HASH_ANNOTATION]

    @staticmethod
    def _compute_hash(spec: ConsulRouterSpec) -> str:
        m: Final = hashlib.sha256()
        m.update(spec.json(by_alias=True, exclude_unset=True).encode())
        return m.hexdigest()

    def _create_crd(self, body: KubernetesResource) -> None:
        client: Final = kubernetes.client.CustomObjectsApi()
        client.create_namespaced_custom_object(
            self.group.group,
            self.group.version,
            self.kind.namespace,
            self.kind.plural,
            body.dict(by_alias=True, exclude_unset=True),
            dry_run="All" if self.dry_run else None,
        )

    def _patch_crd(self, body: KubernetesResource) -> None:
        client: Final = kubernetes.client.CustomObjectsApi()
        client.patch_namespaced_custom_object(
            self.group.group,
            self.group.version,
            self.kind.namespace,
            self.kind.plural,
            self.name,
            body=body.dict(by_alias=True, exclude_unset=True),
            dry_run="All" if self.dry_run else None,
        )

    def update(self, spec: ConsulRouterSpec) -> None:
        current_hash: Final = self._get_crd_hash()
        new_hash: Final = self._compute_hash(spec)

        body: Final = KubernetesResource(
            apiVersion=f"{self.group.group}/{self.group.version}",
            kind=self.kind.kind,
            metadata=KubernetesResourceMetadata(
                namespace=self.kind.namespace,
                name=self.name,
                annotations={HASH_ANNOTATION: self._compute_hash(spec)},
            ),
            spec=spec,
        )

        if self.labels:
            body.metadata.labels = self.labels

        if self.dry_run:
            log.warning("Dry-run mode is on; not making changes")
            log.info(
                "Planning on using this CRD:\n%s",
                pprint.pformat(body.dict(by_alias=True, exclude_unset=True)),
            )

        if current_hash is None:
            log.info("Creating new %s CRD %s", self.kind.kind, self.name)
            self._create_crd(body)
        elif new_hash != current_hash:
            log.info(
                "Patching %s CRD %s (%s != %s)",
                self.kind.kind,
                self.name,
                new_hash,
                current_hash,
            )
            self._patch_crd(body)
        else:
            log.info("Nothing to do for %s CRD %s", self.kind.kind, self.name)

    def delete(self) -> None:
        log.info("Deleting %s CRD %s", self.kind.kind, self.name)
        client: Final = kubernetes.client.CustomObjectsApi()
        client.delete_namespaced_custom_object(
            self.group.group,
            self.group.version,
            self.kind.namespace,
            self.kind.plural,
            self.name,
            dry_run="All" if self.dry_run else None,
        )


class CRDManager:
    def __init__(
        self,
        group: CRDGroup,
        kind: CRDResourceKind,
        pod_id: str,
        services: dict[str, Service],
        crd_def: Type[DefaultCRD],
        *,
        dry_run: bool = False,
    ) -> None:
        self.group = group
        self.kind = kind
        self.pod_id = pod_id
        self.services = services
        self.crd_def = crd_def
        self.dry_run = dry_run

        self.crd_def_inst = crd_def(self.pod_id, self.services)

    def _get_crds(self) -> frozenset[str]:
        client: Final = kubernetes.client.CustomObjectsApi()
        items = map(
            KubernetesResource.parse_obj,
            client.list_namespaced_custom_object(
                self.group.group,
                self.group.version,
                self.kind.namespace,
                self.kind.plural,
                label_selector=f"{DYNAMIC_LABEL}={self.crd_def.tag}",
            )["items"],
        )
        return frozenset(item.metadata.name for item in items)

    def delete_old(self, accounts: Mapping[str, Sequence[str]]) -> None:
        current_services = self._get_crds()
        expected_services = self.crd_def_inst.names(accounts)
        for name in current_services - expected_services:
            crd_updater = CRDUpdater(self.group, self.kind, name, dry_run=self.dry_run)
            crd_updater.delete()

    def update(self, accounts: Mapping[str, Sequence[str]]) -> None:
        for name, spec in self.crd_def_inst.specs(accounts):
            updater = CRDUpdater(
                self.group,
                self.kind,
                name,
                labels={DYNAMIC_LABEL: self.crd_def.tag},
                dry_run=self.dry_run,
            )
            updater.update(spec)

def get_secret(secret_name, namespace):
        client: Final = kubernetes.client.CoreV1Api()
        secret = client.read_namespaced_secret(secret_name, namespace)
        data = {
            key: value for key, value in secret.data.items()
        }
        log.info(data)
        return data['data']
