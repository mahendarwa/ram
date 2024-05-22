import asyncio
import logging
import random
from collections import defaultdict
from typing import AsyncGenerator, Final

import aioboto3

from .utils import tags2dict

log: Final = logging.getLogger(__name__)

ACCOUNT_TAG: Final = "teracloud:account"
SYSTEM_TAG: Final = "teracloud:system"
POD_ID_TAG: Final = "teracloud:pod:id"
RESOURCES: Final = ["ec2:instance", "ecs:service"]


class Accounts:
    def __init__(self, pod_id: str) -> None:
        self.session: Final = aioboto3.Session()
        self.pod_id: Final = pod_id

    async def lookup(self) -> dict[str, set[str]]:
        accounts: defaultdict[str, set[str]] = defaultdict(set)

        async with self.session.client("resourcegroupstaggingapi") as tapi:
            get_resources: Final = tapi.get_paginator("get_resources")
            async for page in get_resources.paginate(
                ResourceTypeFilters=RESOURCES,
                TagFilters=[
                    {"Key": POD_ID_TAG, "Values": [self.pod_id]},
                    {"Key": SYSTEM_TAG},
                ],
            ):
                for tag_mapping_list in page["ResourceTagMappingList"]:
                    tags = tags2dict(tag_mapping_list["Tags"])
                    account = tags.get(ACCOUNT_TAG)
                    system = tags[SYSTEM_TAG]
                    log.debug("%s: %s, %s", tag_mapping_list["ResourceARN"], account, system)
                    if not account:
                        log.error(
                            "%s (%s) does not contain an account",
                            tag_mapping_list["ResourceARN"],
                            system,
                        )
                        continue

                    accounts[account].add(system)

        return accounts

    async def monitor(self, sleep_time: float, sleep_splay: float) -> AsyncGenerator[dict[str, set[str]], None]:
        old_accounts: dict[str, set[str]] = {}
        while True:
            new_accounts = await self.lookup()

            if new_accounts != old_accounts:
                yield new_accounts
                old_accounts = new_accounts
            else:
                log.info("No change")

            # sleep_time = random.uniform(max(5.0, sleep_time - sleep_splay), sleep_time + sleep_splay)
            log.info("Sleeping %.1f seconds", sleep_time)
            await asyncio.sleep(sleep_time)
