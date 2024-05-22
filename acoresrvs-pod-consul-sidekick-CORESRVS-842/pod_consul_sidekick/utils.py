from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types_aiobotocore_resourcegroupstaggingapi.type_defs import TagTypeDef


def tags2dict(tags: list["TagTypeDef"]) -> dict[str, str]:
    return {item["Key"]: item["Value"] for item in tags or []}
