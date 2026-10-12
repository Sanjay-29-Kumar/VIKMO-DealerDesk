import time
import requests
from django.conf import settings
from core.exceptions import SupplierUnavailableException


class SupplierClient:
    """
    Handles paginated requests to the supplier API with:
    - Cursor pagination (follows next_cursor until null)
    - 429 rate limit backoff (reads Retry-After)
    - 5xx transient error exponential backoff
    - Max 5 attempts per request
    - All-or-nothing failure detection
    """

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = (base_url or settings.SUPPLIER_API_URL).rstrip("/")
        self.api_key = api_key or settings.SUPPLIER_API_KEY
        self.session = requests.Session()
        self.requests_made = 0
        self.pages_fetched = 0

    def fetch_all_products(self) -> tuple[list[dict], int, int]:
        """
        Fetches all pages from the supplier API.
        Returns: (all_items, pages_fetched, requests_made)
        Raises: SupplierUnavailableException if any page fails after 5 attempts or key is invalid.
        """
        all_items = []
        cursor = None
        max_attempts = 5

        while True:
            params = {"limit": 20}
            if cursor:
                params["cursor"] = cursor

            headers = {"X-Api-Key": self.api_key}
            url = f"{self.base_url}/v1/products"

            page_success = False
            page_data = None

            for attempt in range(1, max_attempts + 1):
                self.requests_made += 1
                try:
                    resp = self.session.get(url, params=params, headers=headers, timeout=25)
                    
                    if resp.status_code == 200:
                        page_data = resp.json()
                        page_success = True
                        self.pages_fetched += 1
                        break
                    
                    if resp.status_code == 401:
                        # Invalid API key - immediate failure
                        raise SupplierUnavailableException("Supplier API key invalid (401).")

                    if resp.status_code == 429:
                        # Rate limited: read Retry-After header
                        retry_after = 1
                        header_val = resp.headers.get("Retry-After")
                        if header_val:
                            try:
                                retry_after = max(1, int(header_val))
                            except ValueError:
                                retry_after = 1
                        time.sleep(retry_after)
                        continue

                    if resp.status_code in (500, 502, 503, 504):
                        # Transient server failure: short exponential backoff
                        time.sleep(0.5 * (2 ** (attempt - 1)))
                        continue

                    # Any other client error (e.g. 400, 404)
                    raise SupplierUnavailableException(f"Supplier API returned unexpected HTTP {resp.status_code}.")

                except (requests.ConnectionError, requests.Timeout) as e:
                    if attempt >= max_attempts:
                        raise SupplierUnavailableException(f"Supplier API connection failed after {max_attempts} attempts: {e}")
                    time.sleep(0.5 * (2 ** (attempt - 1)))

            if not page_success:
                raise SupplierUnavailableException(f"Failed to fetch supplier page after {max_attempts} attempts.")

            items = page_data.get("items", [])
            all_items.extend(items)

            cursor = page_data.get("next_cursor")
            if not cursor:
                break

        return all_items, self.pages_fetched, self.requests_made
