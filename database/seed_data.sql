-- ============================================================
-- WasteWise AI — Seed Data (MySQL 8.4 compatible)
-- ============================================================
-- Small, realistic sample dataset for development and testing.
-- Safe to run multiple times: uses INSERT ... ON DUPLICATE KEY UPDATE
-- which updates existing rows instead of duplicating them.
-- ============================================================

-- -----------------------------------------------------
-- Seed: products
-- -----------------------------------------------------
INSERT INTO `products` (
    `product_id`, `product_name`, `category`, `shelf_life_days`,
    `selling_price`, `unit_cost`
) VALUES
    (1001, 'Milk 500ml', 'Dairy', 5, 32.00, 24.00),
    (1002, 'Yogurt Cup', 'Dairy', 10, 25.00, 17.00),
    (1003, 'Bread Loaf', 'Bakery', 4, 40.00, 26.00),
    (1004, 'Paneer 200g', 'Dairy', 7, 85.00, 62.00),
    (1005, 'Apple', 'Produce', 7, 15.00, 9.00),
    (1006, 'Tomato', 'Produce', 5, 20.00, 12.00)
ON DUPLICATE KEY UPDATE
    `product_name` = VALUES(`product_name`),
    `category` = VALUES(`category`),
    `shelf_life_days` = VALUES(`shelf_life_days`),
    `selling_price` = VALUES(`selling_price`),

-- -----------------------------------------------------
-- Seed: inventory_batches
-- -----------------------------------------------------
INSERT INTO `inventory_batches` (
    `batch_id`, `product_id`, `category`, `received_at`,
    `snapshot_date`, `expiry_date`, `initial_quantity`,
    `quantity_remaining`, `days_to_expiry`, `avg_daily_sales_7d`,
    `expected_demand_before_expiry`, `unit_price`, `unit_cost`,
    `discount_pct`, `expiry_risk_label`, `waste_units_actual_simulated`
) VALUES
    (5001, 1006, 'Produce', '2026-08-14 08:00:00', '2026-08-16', '2026-08-21', 140, 72, 5, 23.38, 117.00, 45.00, 28.00, 5.00, 1, 64),
    (5002, 1006, 'Produce', '2026-07-17 08:00:00', '2026-07-23', '2026-07-24', 140, 123, 1, 36.86, 37.00, 45.00, 28.00, 10.00, 1, 31),
    (5003, 1001, 'Dairy', '2026-08-18 08:00:00', '2026-08-20', '2026-08-23', 22, 3, 3, 12.67, 38.00, 32.00, 24.00, 10.00, 1, 3),
    (5004, 1003, 'Bakery', '2026-08-21 08:00:00', '2026-08-26', '2026-08-25', 141, 141, -1, 14.52, 0.00, 40.00, 26.00, 10.00, 1, 114),
    (5005, 1005, 'Produce', '2026-08-19 08:00:00', '2026-08-19', '2026-08-22', 100, 45, 3, 10.00, 30.00, 15.00, 9.00, 0.00, 0, 0),
    (5006, 1002, 'Dairy', '2026-08-15 08:00:00', '2026-08-16', '2026-08-25', 80, 60, 9, 5.50, 49.50, 25.00, 17.00, 0.00, 0, 0)
ON DUPLICATE KEY UPDATE
    `product_id` = VALUES(`product_id`),
    `category` = VALUES(`category`),
    `received_at` = VALUES(`received_at`),
    `snapshot_date` = VALUES(`snapshot_date`),
    `expiry_date` = VALUES(`expiry_date`),
    `initial_quantity` = VALUES(`initial_quantity`),
    `quantity_remaining` = VALUES(`quantity_remaining`),
    `days_to_expiry` = VALUES(`days_to_expiry`),
    `avg_daily_sales_7d` = VALUES(`avg_daily_sales_7d`),
    `expected_demand_before_expiry` = VALUES(`expected_demand_before_expiry`),
    `unit_price` = VALUES(`unit_price`),
    `unit_cost` = VALUES(`unit_cost`),
    `discount_pct` = VALUES(`discount_pct`),
    `expiry_risk_label` = VALUES(`expiry_risk_label`),
    `waste_units_actual_simulated` = VALUES(`waste_units_actual_simulated`);

-- -----------------------------------------------------
-- Seed: perishable_inventory
-- -----------------------------------------------------
INSERT INTO `perishable_inventory` (
    `product_id`, `record_date`, `category`, `opening_stock`,
    `units_received`, `units_sold`, `unit_price`, `discount_pct`,
    `days_to_expiry`, `temperature_c`, `waste_units`, `stockout_flag`
) VALUES
    (1001, '2026-04-01', 'Dairy', 27, 0, 6, 32.00, 0.00, 1, 4.10, 0, 0),
    (1001, '2026-04-02', 'Dairy', 30, 12, 5, 32.00, 0.00, 5, 3.70, 0, 0),
    (1001, '2026-04-03', 'Dairy', 38, 0, 14, 32.00, 0.00, 2, 4.60, 0, 0),
    (1001, '2026-04-04', 'Dairy', 49, 0, 11, 32.00, 0.00, 0, 5.70, 0, 0),
    (1003, '2026-08-21', 'Bakery', 141, 0, 0, 40.00, 10.00, -1, NULL, 0, 0),
    (1006, '2026-08-16', 'Produce', 72, 0, 10, 45.00, 5.00, 5, 4.20, 2, 0)
ON DUPLICATE KEY UPDATE
    `product_id` = VALUES(`product_id`),
    `record_date` = VALUES(`record_date`),
    `category` = VALUES(`category`),
    `opening_stock` = VALUES(`opening_stock`),
    `units_received` = VALUES(`units_received`),
    `units_sold` = VALUES(`units_sold`),
    `unit_price` = VALUES(`unit_price`),
    `discount_pct` = VALUES(`discount_pct`),
    `days_to_expiry` = VALUES(`days_to_expiry`),
    `temperature_c` = VALUES(`temperature_c`),
    `waste_units` = VALUES(`waste_units`),
    `stockout_flag` = VALUES(`stockout_flag`);

-- -----------------------------------------------------
-- Seed: discount_recommendations
-- -----------------------------------------------------
INSERT INTO `discount_recommendations` (
    `batch_id`, `product_id`, `days_to_expiry`,
    `quantity_remaining`, `discount_pct`, `predicted_gross_margin`
) VALUES
    (5001, 1006, 5, 72, 0.00, 1224.00),
    (5002, 1006, 5, 123, 10.00, 900.00),
    (5003, 1001, 3, 3, 10.00, 90.00),
    (5004, 1003, -1, 141, 10.00, 0.00)
ON DUPLICATE KEY UPDATE
    `product_id` = VALUES(`product_id`),
    `days_to_expiry` = VALUES(`days_to_expiry`),
    `quantity_remaining` = VALUES(`quantity_remaining`),
    `discount_pct` = VALUES(`discount_pct`),
    `predicted_gross_margin` = VALUES(`predicted_gross_margin`);

-- -----------------------------------------------------
-- Seed: calendar (sample dates)
-- -----------------------------------------------------
INSERT INTO `calendar` (
    `date`, `wm_yr_wk`, `weekday`, `wday`, `month`, `year`,
    `event_name_1`, `event_type_1`, `event_name_2`, `event_type_2`,
    `snap_CA`, `snap_TX`, `snap_WI`
) VALUES
    ('2026-08-16', 202633, 'Sunday', 1, 8, 2026, NULL, NULL, NULL, NULL, 0, 0, 0),
    ('2026-08-17', 202633, 'Monday', 2, 8, 2026, NULL, NULL, NULL, NULL, 0, 0, 0),
    ('2026-08-18', 202633, 'Tuesday', 3, 8, 2026, NULL, NULL, NULL, NULL, 0, 0, 0),
    ('2026-08-19', 202633, 'Wednesday', 4, 8, 2026, NULL, NULL, NULL, NULL, 0, 0, 0),
    ('2026-08-20', 202633, 'Thursday', 5, 8, 2026, NULL, NULL, NULL, NULL, 0, 0, 0),
    ('2026-08-21', 202633, 'Friday', 6, 8, 2026, NULL, NULL, NULL, NULL, 0, 0, 0),
    ('2026-08-22', 202633, 'Saturday', 7, 8, 2026, NULL, NULL, NULL, NULL, 0, 0, 0)
ON DUPLICATE KEY UPDATE
    `wm_yr_wk` = VALUES(`wm_yr_wk`),
    `weekday` = VALUES(`weekday`),
    `wday` = VALUES(`wday`),
    `month` = VALUES(`month`),
    `year` = VALUES(`year`);

-- -----------------------------------------------------
-- Seed: forecast_results
-- -----------------------------------------------------
INSERT INTO `forecast_results` (
    `product_id`, `forecast_date`, `target_date`,
    `model_name`, `predicted_waste_units`, `predicted_expiry_risk`
) VALUES
    (1001, '2026-08-16', '2026-08-17', 'food_waste', 2.50, NULL),
    (1003, '2026-08-16', '2026-08-17', 'food_waste', 5.00, NULL),
    (1006, '2026-08-16', '2026-08-17', 'food_waste', 8.00, NULL),
    (1001, '2026-08-16', '2026-08-17', 'expiry_risk', NULL, 0.7500),
    (1003, '2026-08-16', '2026-08-17', 'expiry_risk', NULL, 0.9000),
    (1006, '2026-08-16', '2026-08-17', 'expiry_risk', NULL, 0.6000)
ON DUPLICATE KEY UPDATE
    `forecast_date` = VALUES(`forecast_date`),
    `target_date` = VALUES(`target_date`),
    `model_name` = VALUES(`model_name`),
    `predicted_waste_units` = VALUES(`predicted_waste_units`),
    `predicted_expiry_risk` = VALUES(`predicted_expiry_risk`);
    `unit_cost` = VALUES(`unit_cost`);
