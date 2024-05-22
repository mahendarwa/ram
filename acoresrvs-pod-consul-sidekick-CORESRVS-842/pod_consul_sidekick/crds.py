import itertools
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from operator import itemgetter
from typing import Generator, Mapping, Sequence

from .config import Service, ServiceType
from .crd_utils import construct_intent, construct_routes
from .models import ConsulRouterSpec, ConsulServiceIntentionSpec


class DefaultCRD(metaclass=ABCMeta):
    tag = "undefined"

    def __init__(self, pod_id: str, services: Mapping[str, Service]) -> None:
        self.pod_id = pod_id
        self.services = services

    @abstractmethod
    def names(
        self,
        accounts: Mapping[str, Sequence[str]],
    ) -> frozenset[str]:
        ...

    @abstractmethod
    def specs(
        self,
        accounts: Mapping[str, Sequence[str]],
    ) -> Generator[tuple[str, ConsulRouterSpec], None, None]:
        ...


class SharedServicesCRD(DefaultCRD):
    tag = "shared-services"

    @staticmethod
    def _name(service: str, account: str) -> str:
        return f"shared-{service}-{account}"

    def names(self, accounts: Mapping[str, Sequence[str]]) -> frozenset[str]:
        return frozenset(
            self._name(service, account) for account in accounts.keys() for service in self.services.keys()
        )

    def specs(self, accounts: Mapping[str, Sequence[str]]) -> Generator[tuple[str, ConsulRouterSpec], None, None]:
        for account, systems in sorted(accounts.items()):
            for service, service_detail in sorted(self.services.items()):
                yield self._name(service, account), construct_routes(systems, service_detail.upstreams)


class TenantServicesIntentCRD(DefaultCRD):
    tag = "tenant-intents"

    def __init__(self, pod_int: str, services: Mapping[str, Service]) -> None:
        super().__init__(pod_int, services)
        self.destinations = self._destinations_form_services()

    @staticmethod
    def _name(service: str, account_system: str) -> str:
        return f"{service}-{account_system}"

    def _destinations_form_services(self) -> dict[str, set[str]]:
        destinations: dict[str, set[str]] = defaultdict(set)
        for service_name, service_values in self.services.items():
            for upstream in service_values.upstreams:
                destinations[upstream].add(service_name)

        return destinations

    def _is_shared(self, service: str) -> bool:
        return service in self.services and self.services[service].type is ServiceType.shared

    def names(self, accounts: Mapping[str, Sequence[str]]) -> frozenset[str]:
        accs = accounts.keys()
        systems = list(itertools.chain.from_iterable(accounts.values()))

        names: set[str] = set()
        for destination_name in self.destinations.keys():
            if self._is_shared(destination_name):
                names.update(self._name(destination_name, account) for account in accs)
            else:
                names.update(self._name(destination_name, system) for system in systems)

        return frozenset(names)

    def specs(
        self, accounts: Mapping[str, Sequence[str]]
    ) -> Generator[tuple[str, ConsulServiceIntentionSpec], None, None]:
        for destination_name, source_services in sorted(self.destinations.items(), key=itemgetter(0)):
            if self._is_shared(destination_name):
                raise NotImplementedError("Not implemented yet")
            else:
                for account, systems in sorted(accounts.items(), key=itemgetter(0)):
                    for system in sorted(systems):
                        true_sources: list[str] = []
                        for source in sorted(source_services):
                            true_sources.append(self._name(source, account if self._is_shared(source) else system))

                        yield self._name(destination_name, system), construct_intent(
                            self._name(destination_name, system), true_sources
                        )
