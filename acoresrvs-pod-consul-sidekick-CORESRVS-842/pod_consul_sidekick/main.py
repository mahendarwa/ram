import asyncio
import logging
from typing import Final

from . import config
from .accounts import Accounts
from .azure_accounts import AzureAccounts
from .crd_utils import construct_intent, generate_routes, generate_peeringacceptorspec
from .crds import SharedServicesCRD, TenantServicesIntentCRD
from .k8s import CRDGroup, CRDManager, CRDResourceKind, CRDUpdater, get_secret

log: Final = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    settings: Final = config.Settings()
    router_name = f"{settings.POD_ID}-{settings.ROUTER_NAME_SUFFIX}"
    peering_token_name = f"{settings.POD_ID}-{settings.PEERING_TOKEN_NAME_SUFFIX}"

    log.info(
        "Updating every %.1f (+/- %.1f) seconds", settings.SLEEP, settings.SLEEP_SPLAY
    )
    log.info("Managed services: %s", ", ".join(settings.SERVICES))

    # services with shared flag (not B/G upgrade) e.g. pogrouter
    shared_services = dict(
        filter(
            lambda x: x[1].type is config.ServiceType.shared, settings.SERVICES.items()
        )
    )
    log.info("Shared services: %s", ", ".join(shared_services))

    # services running on the POD level
    pod_services = dict(
        filter(lambda x: x[1].type is config.ServiceType.pod, settings.SERVICES.items())
    )
    log.info("POD services: %s", ", ".join(pod_services))

    CRDUpdater.initialize()

    accounts_checker: Final = get_account(settings)
    pod_peering_token_crd_updater = CRDUpdater(
        CRDGroup(settings.RESOURCE_GROUP, settings.RESOURCE_VERSION),
        CRDResourceKind(
            settings.NAMESPACE,
            settings.PEERINGACCEPTOR_RESOURCE_KIND,
            settings.PEERINGACCEPTOR_RESOURCE_PLURAL
        ),
        peering_token_name,
        dry_run=settings.dry_run
    )
    pod_level_crd_updater = CRDUpdater(
        CRDGroup(settings.RESOURCE_GROUP, settings.RESOURCE_VERSION),
        CRDResourceKind(
            settings.NAMESPACE,
            settings.ROUTER_RESOURCE_KIND,
            settings.ROUTER_RESOURCE_PLURAL,
        ),
        router_name,
        dry_run=settings.dry_run,
    )
    main_intent_crd_updater = CRDUpdater(
        CRDGroup(settings.RESOURCE_GROUP, settings.RESOURCE_VERSION),
        CRDResourceKind(
            settings.NAMESPACE,
            settings.INTENT_RESOURCE_KIND,
            settings.INTENT_RESOURCE_PLURAL,
        ),
        router_name,
        dry_run=settings.dry_run,
    )
    shared_services_manager = CRDManager(
        CRDGroup(settings.RESOURCE_GROUP, settings.RESOURCE_VERSION),
        CRDResourceKind(
            settings.NAMESPACE,
            settings.ROUTER_RESOURCE_KIND,
            settings.ROUTER_RESOURCE_PLURAL,
        ),
        settings.POD_ID,
        shared_services,
        SharedServicesCRD,
        dry_run=settings.dry_run,
    )
    tenant_services_intent_manager = CRDManager(
        CRDGroup(settings.RESOURCE_GROUP, settings.RESOURCE_VERSION),
        CRDResourceKind(
            settings.NAMESPACE,
            settings.INTENT_RESOURCE_KIND,
            settings.INTENT_RESOURCE_PLURAL,
        ),
        settings.POD_ID,
        settings.SERVICES,
        TenantServicesIntentCRD,
        dry_run=settings.dry_run,
    )

    # peering acceptor token for pod
    peering_token_spec = generate_peeringacceptorspec(secret_name = f"peering-token-{settings.POD_ID}")
    pod_peering_token_crd_updater.update(peering_token_spec)
    peering_token = get_secret(f"peering-token-{settings.POD_ID}", settings.NAMESPACE)
    log.info("peering token generated")
    log.info(peering_token)

    async for accounts in accounts_checker.monitor(
        settings.SLEEP, settings.SLEEP_SPLAY
    ):

        # router for POD services ([pod id]-tenant-services)
        router_spec = generate_routes(accounts, settings.SERVICES)
        pod_level_crd_updater.update(router_spec)

        # intents for POD services ([pod id]-tenant-services)
        intent_spec = construct_intent(router_name, pod_services)
        main_intent_crd_updater.update(intent_spec)

        # routers for shared services (tenant) (shared-[service]-[account])
        shared_services_manager.delete_old(accounts)
        shared_services_manager.update(accounts)

        # intents for tenant services ([service]-[system/account])
        tenant_services_intent_manager.delete_old(accounts)
        tenant_services_intent_manager.update(accounts)


def get_account(settings):
    return (
        AzureAccounts(settings.POD_ID, settings.SUBSCRIPTION_ID)
        if settings.CLOUD == "AZURE"
        else Accounts(settings.POD_ID)
    )


def cli() -> None:
    asyncio.run(main())
