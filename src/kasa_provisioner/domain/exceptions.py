"""Domain exceptions for kasa-provisioner."""


class KasaProvisionerError(Exception):
    """Base exception for all provisioner errors."""


class ConnectionError(KasaProvisionerError):
    """Cannot reach device at given host/port."""


class ProvisioningError(KasaProvisionerError):
    """Bootstrap provisioning failed."""


class AuthenticationError(KasaProvisionerError):
    """KLAP authentication failed for all credential candidates."""


class DiscoveryError(KasaProvisionerError):
    """No devices found on local network."""


class ControlError(KasaProvisionerError):
    """Power control command failed."""
