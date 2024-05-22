from enum import StrEnum, auto
from typing import Optional

import pydantic
from pydantic import Field


class ConsulRouteMatchHttpHeader(pydantic.BaseModel):
    name: str
    exact: Optional[str]
    regex: Optional[str]


class ConsulRouteMatchHttp(pydantic.BaseModel):
    path_prefix: Optional[str] = Field(None, alias="pathPrefix")
    header: Optional[list[ConsulRouteMatchHttpHeader]]


class ConsulRouteMatch(pydantic.BaseModel):
    http: ConsulRouteMatchHttp


class ConsulRouteDestination(pydantic.BaseModel):
    prefix_rewrite: str = Field(None, alias="prefixRewrite")
    service: str
    request_timeout: str = Field(None, alias="requestTimeout")


class ConsulRoute(pydantic.BaseModel):
    match: ConsulRouteMatch
    destination: ConsulRouteDestination


class ConsulRouterSpec(pydantic.BaseModel):
    routes: list[ConsulRoute]


class ConsulSourceIntentionAction(StrEnum):
    allow = auto()
    deny = auto()


class ConsulSourceIntention(pydantic.BaseModel):
    name: str
    action: ConsulSourceIntentionAction = ConsulSourceIntentionAction.allow
    type: str = "consul"
    description: Optional[str]

    class Config:
        use_enum_values = True


class ConsulServiceIntentionDestination(pydantic.BaseModel):
    name: str


class ConsulServiceIntentionSpec(pydantic.BaseModel):
    destination: ConsulServiceIntentionDestination
    sources: list[ConsulSourceIntention]


class KubernetesResourceMetadata(pydantic.BaseModel):
    namespace: str
    name: str
    annotations: Optional[dict[str, str]]
    labels: Optional[dict[str, str]]


class Secret(pydantic.BaseModel):
    name: str
    key: str
    backend: str


class Peer(pydantic.BaseModel):
    secret: Secret


class PeeringAcceptorSpec(pydantic.BaseModel):
    peer: Peer


class KubernetesResource(pydantic.BaseModel):
    api_version: str = Field(..., alias="apiVersion")
    kind: str
    metadata: KubernetesResourceMetadata
    spec: ConsulRouterSpec | ConsulServiceIntentionSpec | PeeringAcceptorSpec
