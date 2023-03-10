import urllib.request


def get_public_ip() -> str:
    return (
        urllib.request.urlopen("http://checkip.amazonaws.com")
        .read()
        .decode("utf-8")
        .strip()
        + "/32"
    )
