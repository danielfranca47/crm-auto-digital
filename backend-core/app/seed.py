from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models


def get_or_create_product(db: Session, code: str, name: str, description: str = "") -> models.Product:
    product = db.query(models.Product).filter(models.Product.code == code).first()
    if product:
        return product
    product = models.Product(code=code, name=name, description=description, is_active=True)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def get_or_create_plan(
    db: Session,
    product: models.Product,
    code: str,
    name: str,
    billing_period: str = "monthly",
) -> models.Plan:
    plan = db.query(models.Plan).filter(models.Plan.code == code).first()
    if plan:
        return plan
    plan = models.Plan(
        product_id=product.id,
        code=code,
        name=name,
        billing_period=billing_period,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def ensure_plan_limits(db: Session, plan: models.Plan, limits_data: Dict) -> models.PlanLimits:
    limits = db.query(models.PlanLimits).filter(models.PlanLimits.plan_id == plan.id).first()
    if not limits:
        limits = models.PlanLimits(plan_id=plan.id)
    for key, value in limits_data.items():
        setattr(limits, key, value)
    db.add(limits)
    db.commit()
    db.refresh(limits)
    return limits


def seed_initial_data(db: Session) -> None:
    # Garantir coluna nova (SQLite não cria em create_all se tabela já existir)
    try:
        existing_cols = db.execute(text("PRAGMA table_info(plan_limits)")).fetchall()
        if existing_cols is not None and "max_prospects_daily" not in {row[1] for row in existing_cols}:
            db.execute(text("ALTER TABLE plan_limits ADD COLUMN max_prospects_daily INTEGER"))
            db.commit()
    except Exception:
        pass

    try:
        ai_cols = db.execute(text("PRAGMA table_info(ai_profiles)")).fetchall()
        if ai_cols is not None and "custom_variables" not in {row[1] for row in ai_cols}:
            db.execute(text("ALTER TABLE ai_profiles ADD COLUMN custom_variables JSON"))
            db.commit()
    except Exception:
        pass

    products_seed = [
        {"code": "crm", "name": "CRM AutoDigital", "description": ""},
        {"code": "conversational_ai", "name": "Conversational AI", "description": ""},
    ]

    plans_seed: List[Dict] = [
        # Planos legados — mantidos para não quebrar assinaturas existentes
        {"product_code": "crm", "code": "crm_free", "name": "CRM Free"},
        {"product_code": "crm", "code": "crm_basic", "name": "CRM Basic"},
        {"product_code": "crm", "code": "crm_pro", "name": "CRM Pro"},
        {"product_code": "conversational_ai", "code": "conversational_ai_basic", "name": "Conversational AI Basic"},
        {"product_code": "conversational_ai", "code": "conversational_ai_pro", "name": "Conversational AI Pro"},
        # Planos comerciais Digital Pro
        {"product_code": "crm", "code": "crm_start", "name": "Start"},
        {"product_code": "crm", "code": "crm_growth", "name": "Growth"},
        {"product_code": "crm", "code": "crm_internal", "name": "Interno"},
    ]

    limits_seed: Dict[str, Dict] = {
        "crm_free": {
            "max_leads": 100,
            "max_agents_local": 1,
            "max_pesquisa_selenium_daily": 5,
            "max_pesquisa_turbo_monthly": 0,
            "max_prospec_monthly": 0,
            "max_copy_generation_monthly": 25,
            "max_ia_conversas_monthly": 0,
            "max_whatsapp_send_daily": 15,
            "max_prospects_daily": 15,
            "max_maps_search_daily": 10,
            "max_maps_enrich_daily": 20,
            "require_agent_local_activation_fee": True,
            "ia_memory_advanced": False,
        },
        "crm_basic": {
            "max_leads": 1000,
            "max_agents_local": 1,
            "max_pesquisa_selenium_daily": None,
            "max_pesquisa_turbo_monthly": 200,
            "max_prospec_monthly": 200,
            "max_copy_generation_monthly": 500,
            "max_ia_conversas_monthly": 20,
            "max_whatsapp_send_daily": 30,
            "max_prospects_daily": 30,
            "max_maps_search_daily": None,
            "max_maps_enrich_daily": 200,
            "require_agent_local_activation_fee": False,
            "ia_memory_advanced": False,
        },
        "crm_pro": {
            "max_leads": 5000,
            "max_agents_local": 3,
            "max_pesquisa_selenium_daily": None,
            "max_pesquisa_turbo_monthly": 850,
            "max_prospec_monthly": None,
            "max_copy_generation_monthly": 3000,
            "max_ia_conversas_monthly": 200,
            "max_whatsapp_send_daily": 100,
            "max_prospects_daily": 100,
            "max_maps_search_daily": None,
            "max_maps_enrich_daily": None,
            "require_agent_local_activation_fee": False,
            "ia_memory_advanced": False,
        },
        "conversational_ai_basic": {
            "max_leads": None,
            "max_agents_local": None,
            "max_pesquisa_selenium_daily": None,
            "max_pesquisa_turbo_monthly": None,
            "max_prospec_monthly": None,
            "max_copy_generation_monthly": None,
            "max_ia_conversas_monthly": 100,
            "max_whatsapp_send_daily": None,
            "max_prospects_daily": None,
            "max_maps_search_daily": None,
            "max_maps_enrich_daily": None,
            "require_agent_local_activation_fee": False,
            "ia_memory_advanced": False,
        },
        "conversational_ai_pro": {
            "max_leads": None,
            "max_agents_local": None,
            "max_pesquisa_selenium_daily": None,
            "max_pesquisa_turbo_monthly": None,
            "max_prospec_monthly": None,
            "max_copy_generation_monthly": None,
            "max_ia_conversas_monthly": 100,
            "max_whatsapp_send_daily": None,
            "max_prospects_daily": None,
            "max_maps_search_daily": None,
            "max_maps_enrich_daily": None,
            "require_agent_local_activation_fee": False,
            "ia_memory_advanced": True,
        },
        # Planos comerciais Digital Pro
        "crm_start": {
            "max_leads": 500,
            "max_agents_local": 1,
            "max_pesquisa_selenium_daily": None,
            "max_pesquisa_turbo_monthly": None,
            "max_prospec_monthly": None,
            "max_copy_generation_monthly": None,
            "max_ia_conversas_monthly": 250,
            "max_whatsapp_send_daily": 50,
            "max_prospects_daily": None,
            "max_maps_search_daily": None,
            "max_maps_enrich_daily": None,
            "require_agent_local_activation_fee": False,
            "ia_memory_advanced": False,
            "follow_up_enabled": False,
            "playground_monthly_limit": 5,
        },
        "crm_growth": {
            "max_leads": 1500,
            "max_agents_local": 1,
            "max_pesquisa_selenium_daily": None,
            "max_pesquisa_turbo_monthly": None,
            "max_prospec_monthly": None,
            "max_copy_generation_monthly": None,
            "max_ia_conversas_monthly": 500,
            "max_whatsapp_send_daily": 100,
            "max_prospects_daily": None,
            "max_maps_search_daily": None,
            "max_maps_enrich_daily": None,
            "require_agent_local_activation_fee": False,
            "ia_memory_advanced": False,
            "follow_up_enabled": True,
            "playground_monthly_limit": None,
        },
        "crm_internal": {
            "max_leads": None,
            "max_agents_local": None,
            "max_pesquisa_selenium_daily": None,
            "max_pesquisa_turbo_monthly": None,
            "max_prospec_monthly": None,
            "max_copy_generation_monthly": None,
            "max_ia_conversas_monthly": None,
            "max_whatsapp_send_daily": None,
            "max_prospects_daily": None,
            "max_maps_search_daily": None,
            "max_maps_enrich_daily": None,
            "require_agent_local_activation_fee": False,
            "ia_memory_advanced": True,
            "follow_up_enabled": True,
            "playground_monthly_limit": None,
        },
    }

    products: Dict[str, models.Product] = {}
    for product_data in products_seed:
        product = get_or_create_product(db, **product_data)
        products[product.code] = product

    plans: Dict[str, models.Plan] = {}
    for plan_data in plans_seed:
        product = products[plan_data["product_code"]]
        plan = get_or_create_plan(db, product=product, code=plan_data["code"], name=plan_data["name"])
        plans[plan.code] = plan

    for plan_code, limits_data in limits_seed.items():
        plan = plans.get(plan_code)
        if not plan:
            continue
        ensure_plan_limits(db, plan=plan, limits_data=limits_data)
