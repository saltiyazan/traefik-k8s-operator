# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import PropertyMock, patch

import ops.testing
from ops.testing import Harness

from charm import TraefikIngressCharm

ops.testing.SIMULATE_CAN_CONNECT = True


class TlsWithExternalHostname(unittest.TestCase):
    @patch(
        "charm.TraefikIngressCharm._get_loadbalancer_status",
        new_callable=PropertyMock,
        return_value="10.0.0.1",
    )
    def setUp(self, mock_get_loadbalancer_status):
        self.harness: Harness[TraefikIngressCharm] = Harness(TraefikIngressCharm)
        self.harness.set_model_name("test-model")
        self.addCleanup(self.harness.cleanup)
        self.harness.handle_exec("traefik", ["update-ca-certificates", "--fresh"], result=0)
        self.harness.handle_exec(
            "traefik", ["find", "/opt/traefik/juju", "-name", "*.yaml", "-delete"], result=0
        )

        patcher = patch.object(TraefikIngressCharm, "version", property(lambda *_: "0.0.0"))
        self.mock_version = patcher.start()
        self.addCleanup(patcher.stop)

        self.harness.set_leader(True)
        self.harness.begin_with_initial_hooks()
        self.harness.container_pebble_ready("traefik")

    @patch(
        "charm.TraefikIngressCharm._get_loadbalancer_status",
        new_callable=PropertyMock,
        return_value="10.0.0.1",
    )
    def test_external_hostname_is_set_after_relation_joins(self, mock_get_loadbalancer_status):
        # GIVEN an external hostname is not set
        self.assertFalse(self.harness.charm.config.get("external_hostname"))
        self.assertEqual(self.harness.charm.external_host, "10.0.0.1")

        # WHEN a "certificates" relation is formed
        # THEN the charm logs an appropriate DEBUG line
        self.rel_id = self.harness.add_relation("certificates", "root-ca")
        self.harness.add_relation_unit(self.rel_id, "root-ca/0")

        # AND WHEN an external hostname is set
        self.harness.update_config({"external_hostname": "testhostname"})
        self.assertEqual(self.harness.charm.external_host, "testhostname")
        # AND when a root ca joins

        self.harness.add_relation_unit(self.rel_id, "root-ca/0")

        # THEN a CSR is sent
        unit_databag = self.harness.get_relation_data(self.rel_id, self.harness.charm.unit.name)
        self.assertIsNotNone(unit_databag.get("certificate_signing_requests"))

    def test_external_hostname_is_set_before_relation_joins(self):
        # GIVEN an external hostname is set
        self.harness.update_config({"external_hostname": "testhostname"})
        self.assertEqual(self.harness.charm.external_host, "testhostname")

        # WHEN a "certificates" relation is formed
        self.rel_id = self.harness.add_relation("certificates", "root-ca")
        self.harness.add_relation_unit(self.rel_id, "root-ca/0")

        # THEN a CSR is sent
        unit_databag = self.harness.get_relation_data(self.rel_id, self.harness.charm.unit.name)
        self.assertIsNotNone(unit_databag.get("certificate_signing_requests"))
