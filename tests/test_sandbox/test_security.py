from ade.sandbox.security import SandboxSecurityPolicy


def test_default_policy():
    """Default policy should have sensible security defaults."""
    policy = SandboxSecurityPolicy()
    assert policy.memory_limit == "512m"
    assert policy.cpu_limit == 1.0
    assert policy.network_disabled is True
    assert policy.cap_drop == ["ALL"]
    assert policy.pids_limit == 256


def test_to_container_kwargs_structure():
    """to_container_kwargs should produce valid docker-py kwargs."""
    policy = SandboxSecurityPolicy(
        memory_limit="256m",
        cpu_limit=0.5,
        network_disabled=False,
    )
    kwargs = policy.to_container_kwargs()

    assert kwargs["mem_limit"] == "256m"
    assert kwargs["nano_cpus"] == 500_000_000
    assert kwargs["network_disabled"] is False
    assert kwargs["cap_drop"] == ["ALL"]
    assert kwargs["security_opt"] == ["no-new-privileges"]
    assert kwargs["pids_limit"] == 256


def test_custom_capabilities():
    """Should allow adding specific capabilities."""
    policy = SandboxSecurityPolicy(cap_add=["NET_BIND_SERVICE"])
    kwargs = policy.to_container_kwargs()
    assert kwargs["cap_add"] == ["NET_BIND_SERVICE"]


def test_no_cap_add_returns_none():
    """Empty cap_add should produce None in kwargs."""
    policy = SandboxSecurityPolicy()
    kwargs = policy.to_container_kwargs()
    assert kwargs["cap_add"] is None
