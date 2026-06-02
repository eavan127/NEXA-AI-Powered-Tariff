import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from calculator.landed_cost import compute_sku_costs, get_anti_dumping_rate

FX = 4.67


class TestAntiDumping:
    def test_china_8541_matches(self):
        assert get_anti_dumping_rate("China", "8541.10") == 5.0

    def test_china_7210_matches(self):
        assert get_anti_dumping_rate("China", "7210.61") == 13.9

    def test_vietnam_7214_matches(self):
        assert get_anti_dumping_rate("Vietnam", "7214.20") == 8.5

    def test_vietnam_8534_no_match(self):
        assert get_anti_dumping_rate("Vietnam", "8534.00") == 0.0

    def test_unknown_origin_no_match(self):
        assert get_anti_dumping_rate("Taiwan", "8541.10") == 0.0


class TestSkuCosts:
    def test_lmw_true_no_duty_no_tax(self):
        sku = {"hs_code": "8534.00", "description": "PCB",
               "quantity": 10, "unit_value_usd": 100.0, "weight_kg": 0.5}
        r = compute_sku_costs(sku, 100.0, 20.0, 1000.0, 5.0, FX, True, 0.0, "Vietnam")
        assert r["regulatory_charges_myr"]["customs_duty_charged"] == 0.0
        assert r["regulatory_charges_myr"]["sales_tax_charged"] == 0.0

    def test_lmw_false_duty_calculated(self):
        sku = {"hs_code": "8501.52", "description": "Motor",
               "quantity": 1, "unit_value_usd": 1000.0, "weight_kg": 10.0}
        r = compute_sku_costs(sku, 0.0, 0.0, 1000.0, 10.0, FX, False, 5.0, "China")
        expected_cif  = round(1000.0 * FX, 4)
        expected_duty = round(expected_cif * 0.05, 4)
        assert r["regulatory_charges_myr"]["customs_duty_charged"] == expected_duty

    def test_sales_tax_compounds_on_cif_plus_duties(self):
        sku = {"hs_code": "8501.52", "description": "Motor",
               "quantity": 1, "unit_value_usd": 1000.0, "weight_kg": 10.0}
        r = compute_sku_costs(sku, 0.0, 0.0, 1000.0, 10.0, FX, False, 5.0, "China")
        cif  = r["apportionment_metrics"]["calculated_cif_myr"]
        duty = r["regulatory_charges_myr"]["customs_duty_charged"]
        add  = r["regulatory_charges_myr"]["anti_dumping_duty_charged"]
        tax  = r["regulatory_charges_myr"]["sales_tax_charged"]
        assert tax == round(0.10 * (cif + duty + add), 4)

    def test_freight_apportioned_by_weight(self):
        sku = {"hs_code": "8534.00", "description": "PCB",
               "quantity": 1, "unit_value_usd": 100.0, "weight_kg": 2.0}
        r = compute_sku_costs(sku, 100.0, 0.0, 500.0, 10.0, FX, True, 0.0, "Vietnam")
        # weight 2/10 = 20%
        assert r["apportionment_metrics"]["allocated_freight_usd"] == round(100.0 * (2.0 / 10.0), 4)

    def test_insurance_apportioned_by_value(self):
        sku = {"hs_code": "8534.00", "description": "PCB",
               "quantity": 1, "unit_value_usd": 250.0, "weight_kg": 1.0}
        r = compute_sku_costs(sku, 0.0, 50.0, 500.0, 5.0, FX, True, 0.0, "Vietnam")
        # value 250/500 = 50%
        assert r["apportionment_metrics"]["allocated_insurance_usd"] == round(50.0 * 0.5, 4)

    def test_add_triggered_for_china_8541(self):
        sku = {"hs_code": "8541.10", "description": "Diode",
               "quantity": 1, "unit_value_usd": 1000.0, "weight_kg": 0.1}
        r = compute_sku_costs(sku, 0.0, 0.0, 1000.0, 0.1, FX, True, 0.0, "China")
        cif          = r["apportionment_metrics"]["calculated_cif_myr"]
        expected_add = round(cif * 0.05, 4)
        assert r["regulatory_charges_myr"]["anti_dumping_duty_charged"] == expected_add
        assert r["flags_applied"]["anti_dumping_matched"] is True

    def test_freight_fallback_to_value_when_weight_zero(self):
        sku = {"hs_code": "8534.00", "description": "PCB",
               "quantity": 1, "unit_value_usd": 200.0, "weight_kg": 0.0}
        r = compute_sku_costs(sku, 100.0, 0.0, 400.0, 0.0, FX, True, 0.0, "Vietnam")
        # value fallback: 200/400 = 50%
        assert r["apportionment_metrics"]["allocated_freight_usd"] == round(100.0 * 0.5, 4)
