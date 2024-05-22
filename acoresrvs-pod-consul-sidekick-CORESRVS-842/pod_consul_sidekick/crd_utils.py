import itertools
from typing import Final, Iterable, Sequence

from .config import Service, ServiceType, Settings
from .models import (
    ConsulRoute,
    ConsulRouteDestination,
    ConsulRouteMatch,
    ConsulRouteMatchHttp,
    ConsulRouteMatchHttpHeader,
    ConsulRouterSpec,
    ConsulServiceIntentionDestination,
    ConsulServiceIntentionSpec,
    ConsulSourceIntention,
    ConsulSourceIntentionAction,
    Secret,
    Peer,
    PeeringAcceptorSpec
)

HEADER_SYSTEM_NAME: Final = "X-Destination"
HEADER_SERVICE_NAME: Final = "X-Service"

settings: Final = Settings()


def construct_route(system: str, service: str) -> ConsulRoute:
    service_config = settings.SERVICES.get(service)
    return ConsulRoute(
        match=ConsulRouteMatch(
            http=ConsulRouteMatchHttp(
                header=[
                    ConsulRouteMatchHttpHeader(name=HEADER_SYSTEM_NAME, exact=system),
                    ConsulRouteMatchHttpHeader(name=HEADER_SERVICE_NAME, exact=service),
                ]
            )
        ),
        destination=ConsulRouteDestination(
            service=f"{service}-{system}", requestTimeout=service_config.request_timeout
        ),
    )


def construct_routes(systems: Sequence[str], services: Iterable[str]) -> ConsulRouterSpec:
    return ConsulRouterSpec(
        routes=[construct_route(system, service) for service in sorted(services) for system in sorted(systems)]
    )


def generate_routes(accounts: dict[str, Iterable[str]], services: dict[str, Service]) -> ConsulRouterSpec:
    routes = [
        construct_route(system, service)
        for system in sorted(itertools.chain.from_iterable(accounts.values()))
        for service, service_details in sorted(services.items())
        if service_details.type is ServiceType.default
    ] + [
        construct_route(account, service)
        for account in sorted(accounts.keys())
        for service, service_details in sorted(services.items())
        if service_details.type is ServiceType.shared
    ] + [
        construct_route(account, service)
        for account in sorted(accounts.keys())
        for service, service_details in sorted(services.items())
        if service_details.type is ServiceType.account
    ]
    return ConsulRouterSpec(routes=routes)


def construct_intent(destination: str, sources: Iterable[str]) -> ConsulServiceIntentionSpec:
    source_intentions = [
        ConsulSourceIntention(name=source, action=ConsulSourceIntentionAction.allow) for source in sources
    ]
    return ConsulServiceIntentionSpec(
        destination=ConsulServiceIntentionDestination(name=destination),
        sources=source_intentions,
    )

def generate_peeringacceptorspec(secret_name) -> PeeringAcceptorSpec:
    secret = Secret(name = secret_name, key = "data", backend = "kubernetes")
    peer = Peer(secret = secret)
    return PeeringAcceptorSpec(peer = peer)
