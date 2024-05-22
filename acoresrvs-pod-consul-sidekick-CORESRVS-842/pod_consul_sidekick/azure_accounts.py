import asyncio
import logging
import random
from collections import defaultdict
from typing import AsyncGenerator, Final
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
from .azure_library import ClientAssertionCredential
from azure.identity import DefaultAzureCredential

log: Final = logging.getLogger(__name__)

ACCOUNT_TAG: Final = "teracloud:account"
SYSTEM_TAG: Final = "teracloud:system"
POD_ID_TAG: Final = "teracloud:pod:id"
RESOURCE_TYPE_FILTER: Final = "Microsoft.Compute/virtualMachines,Microsoft.ContainerInstance/containerGroups"


class AzureAccounts:
    def __init__(self, pod_id: str, subscription_id) -> None:
        self.pod_id: Final = pod_id
        self.subscription_id: Final = subscription_id

    async def lookup(self) -> dict[str, set[str]]:
        accounts: defaultdict[str, set[str]] = defaultdict(set)
        credential = ClientAssertionCredential()
        client = ResourceGraphClient(credential)

        # Define the query to retrieve resources with multiple tags
        query = f"""
            where 
                (type =~ 'microsoft.compute/virtualmachines' or type =~ 'microsoft.containerinstance/containergroups') and 
                tags['{POD_ID_TAG}'] =~ '{self.pod_id}' and isnotnull(tags['{SYSTEM_TAG}'])
               
        """
        log.info(f"query to fetch accounts: {query}")
        # Execute the query and retrieve the results
        request = QueryRequest(subscriptions=[self.subscription_id], query=query)
        response = client.resources(request)
        # Print the resource IDs and tags
        for resource in response.data:
            account = resource["tags"].get(ACCOUNT_TAG)
            system = resource["tags"][SYSTEM_TAG]
            if not account:
                log.error(
                    "%s (%s) does not contain an account",
                    resource["id"],
                    system,
                )
                continue

            accounts[account].add(system)
        log.info(f"Total accounts: {accounts}")
        return accounts

    async def monitor(self, sleep_time: float, sleep_splay: float) -> AsyncGenerator[dict[str, set[str]], None]:
        old_accounts: dict[str, set[str]] = {}
        while True:
            new_accounts = await self.lookup()
            log.info(f"Old Accounts :{old_accounts}")
            log.info(f"New Accounts :{new_accounts}")

            if new_accounts != old_accounts:
                yield new_accounts
                old_accounts = new_accounts
            else:
                log.info("No change")

            # sleep_time = random.uniform(max(5.0, sleep_time - sleep_splay), sleep_time + sleep_splay)
            log.info("Sleeping %.1f seconds", sleep_time)
            await asyncio.sleep(sleep_time)
