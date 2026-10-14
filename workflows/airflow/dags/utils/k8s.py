"""Utilities for interacting with Kubernetes secrets and configmaps."""

import base64
from dataclasses import dataclass

from kubernetes import client, config
from kubernetes.client import ApiClient
from utils import _current_namespace


def _default_core_v1_api() -> client.CoreV1Api:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api()


@dataclass(frozen=True)
class SecretEntry:
    """A secret entry with its name, key, and decoded value."""

    secret_name: str
    key: str
    value: str


@dataclass(frozen=True)
class ConfigMapEntry:
    """A configmap entry with its name, key, and value."""

    configmap_name: str
    key: str
    value: str


def get_secret_entries(
    secret_name: str,
    keys: list[str],
    namespace: str | None = None,
    kube_client: ApiClient | None = None,
) -> list[SecretEntry]:
    """Fetch values from a Kubernetes secret.

    Args:
        secret_name: Name of the secret
        keys: List of keys to fetch from the secret
        namespace: Kubernetes namespace (default: "default")
        kube_client: Optional Kubernetes client. If not provided, uses the default.

    Returns:
        List of SecretEntry objects with decoded values.
    """
    if kube_client is None:
        kube_client = _default_core_v1_api()
    if namespace is None:
        namespace = _current_namespace()

    try:
        secret = kube_client.read_namespaced_secret(secret_name, namespace)
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return []
        raise

    result = []
    for key in keys:
        if key in secret.data:
            # Secrets are base64 encoded in K8s
            encoded_value = secret.data[key]
            decoded_value = base64.b64decode(encoded_value).decode("utf-8")
            result.append(SecretEntry(secret_name=secret_name, key=key, value=decoded_value))

    return result


def get_configmap_entries(
    configmap_name: str,
    keys: list[str],
    namespace: str | None = None,
    kube_client: ApiClient | None = None,
) -> list[ConfigMapEntry]:
    """Fetch values from a Kubernetes configmap.

    Args:
        configmap_name: Name of the configmap
        keys: List of keys to fetch from the configmap
        namespace: Kubernetes namespace (default: "default")
        kube_client: Optional Kubernetes client. If not provided, uses the default.

    Returns:
        List of ConfigMapEntry objects with values.
    """
    if kube_client is None:
        kube_client = _default_core_v1_api()
    if namespace is None:
        namespace = _current_namespace()

    try:
        configmap = kube_client.read_namespaced_config_map(configmap_name, namespace)
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return []
        raise

    result = []
    for key in keys:
        if key in configmap.data:
            result.append(
                ConfigMapEntry(
                    configmap_name=configmap_name, key=key, value=configmap.data[key]
                )
            )

    return result