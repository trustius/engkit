import time

RETRY_DELAY_SECONDS = 2
MAX_ATTEMPTS = 3


def call_vendor(send):
    for attempt in range(MAX_ATTEMPTS):
        response = send()
        if response.ok:
            return response
        time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError("vendor call failed")
