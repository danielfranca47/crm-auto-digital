import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.api import subscriptions
from app.db import Base
from app.services import checkout_links

CRM_BASE = "https://api.example.com"


class EntitlementsRenewalUrlTests(unittest.TestCase):
    """`renewal_checkout_url` de GET /me/entitlements — o link que o botão "Renovar agora"
    do frontend abre para uma conta sem plano activo."""

    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.user = models.User(email="dono@example.com", password_hash="x", name="Dono")
        self.product = models.Product(code="crm", name="CRM")
        self.db.add_all([self.user, self.product])
        self.db.commit()
        self.growth = models.Plan(product_id=self.product.id, code="crm_growth", name="Growth")
        self.internal = models.Plan(product_id=self.product.id, code="crm_internal", name="Interno")
        self.db.add_all([self.growth, self.internal])
        self.db.commit()

        patcher = patch.object(checkout_links.settings, "CRM_PUBLIC_BASE_URL", CRM_BASE)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.db.close)

    def _add_sub(self, plan, status, origin_offer=None):
        sub = models.Subscription(
            user_id=self.user.id,
            product_id=self.product.id,
            plan_id=plan.id,
            status=status,
            current_period_end=datetime.utcnow() - timedelta(days=3),
            origin_offer=origin_offer,
        )
        self.db.add(sub)
        self.db.commit()
        return sub

    def _entitlements(self):
        return asyncio.run(subscriptions.get_entitlements(current_user=self.user, db=self.db))

    def test_expired_founder_keeps_locked_price(self):
        self._add_sub(self.growth, "expired", origin_offer="growth_fundador")
        result = self._entitlements()
        self.assertEqual(result.subscription_status, "expired")
        self.assertEqual(
            result.products[0].renewal_checkout_url,
            f"{CRM_BASE}/checkout/efi/growth_founder_renewal",
        )

    def test_expired_regular_gets_normal_offer(self):
        self._add_sub(self.growth, "expired", origin_offer="growth")
        result = self._entitlements()
        self.assertEqual(
            result.products[0].renewal_checkout_url, f"{CRM_BASE}/checkout/efi/growth"
        )

    def test_cancelled_founder_goes_back_to_normal_price(self):
        self._add_sub(self.growth, "cancelled", origin_offer="growth_fundador")
        result = self._entitlements()
        self.assertEqual(result.subscription_status, "inactive")
        self.assertEqual(
            result.products[0].renewal_checkout_url, f"{CRM_BASE}/checkout/efi/growth"
        )

    def test_plan_without_sellable_offer_has_no_link(self):
        self._add_sub(self.internal, "expired")
        result = self._entitlements()
        self.assertIsNone(result.products[0].renewal_checkout_url)

    def test_no_link_when_crm_public_base_url_missing(self):
        self._add_sub(self.growth, "expired")
        with patch.object(checkout_links.settings, "CRM_PUBLIC_BASE_URL", None):
            result = self._entitlements()
        self.assertIsNone(result.products[0].renewal_checkout_url)

    def test_email_link_still_falls_back_to_subscription_page(self):
        # Emails precisam sempre de um link clicável — o fallback é só deles.
        self.assertEqual(
            checkout_links.get_checkout_url("crm_internal"),
            checkout_links.FALLBACK_CHECKOUT_URL,
        )


if __name__ == "__main__":
    unittest.main()
