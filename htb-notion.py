#!/usr/bin/env python3
import argparse
import logging
import requests

from template import *


NOTION_API_BASE_URL = "https://api.notion.com/v1"
HTB_BASE_URL = "https://www.hackthebox.com"
HTB_API_BASE_URL = f"{HTB_BASE_URL}/api/v4"


class Machine:
    def __init__(
            self,
            name: str,
            machine_id: int,
            os: str,
            difficulty: str,
            rating: float,
            difficulty_rating: int,
            retired: bool,
            user_own: bool,
            system_own: bool,
            release_date: str,
            avatar_url: str
    ):
        self.name = name
        self.machine_id = machine_id
        self.os = os
        self.difficulty = difficulty
        self.rating = rating
        self.difficulty_rating = difficulty_rating
        self.retired = retired
        self.user_own = user_own
        self.system_own = system_own
        self.release_date = release_date
        self.avatar_url = avatar_url


def get_htb_machines(retired: bool, headers: dict):
    logging.debug(f"Getting {'retired' if retired else 'active'} HTB Machines")

    if retired:
        url = f"{HTB_API_BASE_URL}/machine/list/retired/paginated?per_page=50"
    else:
        url = f"{HTB_API_BASE_URL}/machine/paginated?per_page=50"

    machines = []

    while True:
        logging.debug(f"GET {url}")

        response = requests.get(url, headers=headers)

        if response.status_code != requests.codes.ok:
            logging.error("Fail to get data from HTB API")
            exit(1)

        response = response.json()
        data = response["data"]
        links = response["links"]

        for machine in data:
            machines.append(Machine(
                name=machine["name"],
                machine_id=machine["id"],
                os=machine["os"],
                difficulty=machine["difficultyText"],
                rating=machine["star"],
                difficulty_rating=machine["difficulty"],
                retired=retired,
                user_own=machine["authUserInUserOwns"],
                system_own=machine["authUserInRootOwns"],
                release_date=machine["release"].split("T")[0],
                avatar_url=f"{HTB_BASE_URL}{machine['avatar']}"
            ))
        if links.get("next"):
            url = links["next"]
        else:
            break
    return machines


def get_existing_pages(database_id: str, headers: dict):
    logging.debug("Getting Notion existing pages")

    url = f"{NOTION_API_BASE_URL}/databases/{database_id}/query"
    existing_machines = {}
    data = {}

    while True:
        logging.debug(f"POST {url}")
        logging.debug(data)

        response = requests.post(url, headers=headers, json=data)

        if response.status_code != requests.codes.ok:
            logging.error("Fail to get data from Notion API")
            exit(1)

        response = response.json()
        results = response["results"]

        for page in results:
            page_properties = page["properties"]
            existing_machines[page["properties"]["ID"]["number"]] = {
                "page_id": page["id"],
                "properties": {
                    "Difficulty": {
                        "select": {
                            "name": page_properties["Difficulty"]["select"]["name"]
                        }
                    },
                    "Rating": {
                        "number": page_properties["Rating"]["number"]
                    },
                    "Difficulty Rating": {
                        "number": page_properties["Difficulty Rating"]["number"]
                    },
                    "Retired": {
                        "checkbox": page_properties["Retired"]["checkbox"]
                    },
                    "User Own": {
                        "checkbox": page_properties["User Own"]["checkbox"]
                    },
                    "System Own": {
                        "checkbox": page_properties["System Own"]["checkbox"]
                    }
                }
            }

        if response["has_more"]:
            data = {
                "start_cursor": response["next_cursor"]
            }
        else:
            break
    return existing_machines


def create_page(new_machine: Machine, database_id: str, headers: dict):
    logging.debug(f"Creating page for {new_machine.name}")

    url = f"{NOTION_API_BASE_URL}/pages"
    data = {
        "parent": {
            "database_id": database_id
        },
        "icon": {
            "external": {
                "url": new_machine.avatar_url
            }
        },
        "properties": {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": new_machine.name
                        }
                    }
                ]
            },
            "ID": {
                "number": new_machine.machine_id
            },
            "OS": {
                "select": {
                    "name": new_machine.os
                }
            },
            "Difficulty": {
                "select": {
                    "name": new_machine.difficulty
                }
            },
            "Rating": {
                "number": new_machine.rating
            },
            "Difficulty Rating": {
                "number": new_machine.difficulty_rating
            },
            "Retired": {
                "checkbox": new_machine.retired
            },
            "User Own": {
                "checkbox": new_machine.user_own
            },
            "System Own": {
                "checkbox": new_machine.system_own
            },
            "Release Date": {
                "date": {
                    "start": new_machine.release_date
                }
            }
        },
        "children": NOTION_WRITEUP_TEMPLATE
    }

    logging.debug(f"POST {url}")
    logging.debug(data)

    response = requests.post(url, headers=headers, json=data)

    if response.status_code != requests.codes.ok:
        logging.error("Fail to create page")
        logging.error(response.json())
        exit(1)


def update_page_properties(existing_machine: Machine, existing_page: dict, headers: dict):
    url = f"{NOTION_API_BASE_URL}/pages/{existing_page['page_id']}"
    data = {
        "properties": {
            "Difficulty": {
                "select": {
                    "name": existing_machine.difficulty
                }
            },
            "Rating": {
                "number": existing_machine.rating
            },
            "Difficulty Rating": {
                "number": existing_machine.difficulty_rating
            },
            "Retired": {
                "checkbox": existing_machine.retired
            },
            "User Own": {
                "checkbox": existing_machine.user_own
            },
            "System Own": {
                "checkbox": existing_machine.system_own
            }
        }
    }

    if data["properties"] == existing_page["properties"]:
        return

    logging.debug(f"Updating properties for {existing_machine.name}")
    logging.debug(f"POST {url}")
    logging.debug(data)

    response = requests.patch(url, headers=headers, json=data)

    if response.status_code != requests.codes.ok:
        logging.error(f"Fail to update page properties")
        logging.error(response.json())
        exit(1)


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s - %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description="Import HTB Machines to Notion")

    parser.add_argument("--htb-token", type=str, help="HTB App Token", required=True)
    parser.add_argument("--notion-token", type=str, help="Notion API secret", required=True)
    parser.add_argument("--notion-db", type=str, help="Notion database ID", required=True)
    parser.add_argument("--debug", action="store_true", help="Enable debugging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    htb_api_headers = {
        "Authorization": f"Bearer {args.htb_token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"
    }

    notion_api_headers = {
        "Authorization": f"Bearer {args.notion_token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    htb_retired_machines = get_htb_machines(retired=True, headers=htb_api_headers)
    htb_active_machines = get_htb_machines(retired=False, headers=htb_api_headers)
    htb_all_machines = htb_retired_machines + htb_active_machines

    notion_existing_machines = get_existing_pages(database_id=args.notion_db, headers=notion_api_headers)

    for htb_machine in htb_all_machines:
        if notion_existing_machines.get(htb_machine.machine_id):
            update_page_properties(
                existing_machine=htb_machine,
                existing_page=notion_existing_machines[htb_machine.machine_id],
                headers=notion_api_headers
            )
        else:
            create_page(new_machine=htb_machine, database_id=args.notion_db, headers=notion_api_headers)
