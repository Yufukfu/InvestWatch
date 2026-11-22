import pytest

from iw_scraper.addresses import AddressChecker, AddressRefused


def resolver_for(*answers: str):
    async def resolve(host: str) -> list[str]:
        return list(answers)

    return resolve


async def test_a_public_answer_is_returned():
    assert await AddressChecker(resolver_for("93.184.216.34")).check("example.com") == "93.184.216.34"


@pytest.mark.parametrize("literal", ["127.0.0.1", "169.254.169.254", "10.0.0.5", "::1", "::ffff:127.0.0.1", "64:ff9b::7f00:1"])
async def test_an_internal_literal_is_refused(literal):
    with pytest.raises(AddressRefused) as raised:
        await AddressChecker(resolver_for()).check(literal)
    assert not raised.value.lookup_failed


async def test_one_internal_answer_refuses_the_host_whatever_else_it_returns():
    with pytest.raises(AddressRefused, match="address not allowed"):
        await AddressChecker(resolver_for("93.184.216.34", "10.0.0.5")).check("example.com")


async def test_a_bare_or_listed_internal_name_is_refused_without_a_lookup():
    for name in ("localhost", "minio", "db.corp"):
        with pytest.raises(AddressRefused, match="internal host name"):
            await AddressChecker(resolver_for("93.184.216.34"), internal_hosts=["db.corp"]).check(name)


async def test_a_failed_lookup_is_marked_as_a_lookup_failure():
    async def broken(host: str) -> list[str]:
        raise OSError("no such host")

    with pytest.raises(AddressRefused) as raised:
        await AddressChecker(broken).check("example.com")
    assert raised.value.lookup_failed


async def test_a_resolver_that_never_answers_times_out_as_a_lookup_failure():
    import asyncio

    async def stuck(host: str) -> list[str]:
        await asyncio.sleep(5)
        return []

    with pytest.raises(AddressRefused) as raised:
        await AddressChecker(stuck, timeout=0.05).check("example.com")
    assert raised.value.lookup_failed
