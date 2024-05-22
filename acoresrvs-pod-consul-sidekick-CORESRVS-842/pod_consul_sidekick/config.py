from enum import StrEnum, auto
from typing import List, Optional

import pydantic


class ServiceType(StrEnum):
    # standard tenant service
    default = auto()
    # tenant service running on shared system that doesn't take part in B/G upgrade (e.g. pogrouter)
    shared = auto()
    # pod level service
    pod = auto()
    # service registered in consul with account-id
    account = auto()


class Service(pydantic.BaseModel):
    type: ServiceType = ServiceType.default
    upstreams: set[str] = set()
    request_timeout: str = pydantic.Field(default="15s")


class Settings(pydantic.BaseSettings):
    dry_run: bool = True

    RESOURCE_GROUP: str = "consul.hashicorp.com"
    RESOURCE_VERSION: str = "v1alpha1"
    NAMESPACE: str = "default"
    ROUTER_RESOURCE_KIND: str = "ServiceRouter"
    ROUTER_RESOURCE_PLURAL: str = "servicerouters"
    INTENT_RESOURCE_KIND: str = "ServiceIntentions"
    INTENT_RESOURCE_PLURAL: str = "serviceintentions"
    PEERINGACCEPTOR_RESOURCE_KIND = "PeeringAcceptor"
    PEERINGACCEPTOR_RESOURCE_PLURAL = "peeringacceptors"

    ROUTER_NAME_SUFFIX: str = "tenant-services"
    PEERING_TOKEN_NAME_SUFFIX: str = "peering"

    POD_ID: str
    SERVICES: dict[str, Service]
    SLEEP: float = 2 * 60
    SLEEP_SPLAY: float = 2 * 60 + 20
    CLOUD: str = "AWS"
    SUBSCRIPTION_ID: Optional[str]

    class Config:
        env_nested_delimiter = "__"
