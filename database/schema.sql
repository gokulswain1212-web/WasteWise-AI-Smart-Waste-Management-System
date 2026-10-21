-- ============================================================
-- WasteWise AI — Database Schema (MySQL 8.4 compatible)
-- ============================================================
-- Tables:
--   products              — product catalog
--   inventory_batches     — inventory batches with expiry dates
--   perishable_inventory  — daily waste/sales records
--   discount_recommendations — stored discount scenario results
--   calendar              — date dimension for forecasting
--   forecast_results      — stored ML model predictions
-- ============================================================

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -----------------------------------------------------
-- Table: products
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `products` (
    `product_id` INT UNSIGNED NOT NULL,
    `product_name` VARCHAR(100) NOT NULL,
    `category` VARCHAR(50) NOT NULL,
    `shelf_life_days` INT UNSIGNED NOT NULL,
    `selling_price` DECIMAL(10,2) NOT NULL,
    `unit_cost` DECIMAL(10,2) NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`product_id`),
    INDEX `idx_products_category` (`category`),
    CONSTRAINT `chk_products_shelf_life_positive` CHECK (`shelf_life_days` > 0),
    CONSTRAINT `chk_products_selling_price_non_negative` CHECK (`selling_price` >= 0),
    CONSTRAINT `chk_products_unit_cost_non_negative` CHECK (`unit_cost` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- -----------------------------------------------------
-- Table: inventory_batches
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `inventory_batches` (
    `batch_id` INT UNSIGNED NOT NULL,
    `product_id` INT UNSIGNED NOT NULL,
    `category` VARCHAR(50) NOT NULL,
    `received_at` DATETIME NOT NULL,
    `snapshot_date` DATE NOT NULL,
    `expiry_date` DATE NOT NULL,
    `initial_quantity` INT UNSIGNED NOT NULL,
    `quantity_remaining` INT UNSIGNED NOT NULL,
    `days_to_expiry` INT NOT NULL,
    `avg_daily_sales_7d` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    `expected_demand_before_expiry` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    `unit_price` DECIMAL(10,2) NOT NULL,
    `unit_cost` DECIMAL(10,2) NOT NULL,
    `discount_pct` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    `expiry_risk_label` TINYINT(1) NOT NULL DEFAULT 0,
    `waste_units_actual_simulated` INT UNSIGNED NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`batch_id`),
    INDEX `idx_inventory_batches_product_id` (`product_id`),
    INDEX `idx_inventory_batches_snapshot_date` (`snapshot_date`),
    INDEX `idx_inventory_batches_expiry_date` (`expiry_date`),
    INDEX `idx_inventory_batches_days_to_expiry` (`days_to_expiry`),
    CONSTRAINT `fk_inventory_batches_product`
        FOREIGN KEY (`product_id`)
        REFERENCES `products` (`product_id`)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT `chk_inventory_batches_quantity_remaining_non_negative` CHECK (`quantity_remaining` >= 0),
    CONSTRAINT `chk_inventory_batches_initial_quantity_positive` CHECK (`initial_quantity` > 0),
    CONSTRAINT `chk_inventory_batches_quantity_remaining_le_initial` CHECK (`quantity_remaining` <= `initial_quantity`),
    CONSTRAINT `chk_inventory_batches_discount_pct_range` CHECK (`discount_pct` >= 0 AND `discount_pct` <= 100),
    CONSTRAINT `chk_inventory_batches_expiry_risk_label_binary` CHECK (`expiry_risk_label` IN (0, 1)),
    CONSTRAINT `chk_inventory_batches_waste_units_non_negative` CHECK (`waste_units_actual_simulated` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- -----------------------------------------------------
-- Table: perishable_inventory
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `perishable_inventory` (
    `record_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `product_id` INT UNSIGNED NOT NULL,
    `date` DATE NOT NULL,
    `category` VARCHAR(50) NOT NULL,
    `opening_stock` INT UNSIGNED NOT NULL,
    `units_received` INT UNSIGNED NOT NULL DEFAULT 0,
    `units_sold` INT UNSIGNED NOT NULL DEFAULT 0,
    `unit_price` DECIMAL(10,2) NOT NULL,
    `discount_pct` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    `days_to_expiry` INT NOT NULL,
    `temperature_c` DECIMAL(5,2) DEFAULT NULL,
    `waste_units` INT UNSIGNED NOT NULL DEFAULT 0,
    `stockout_flag` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`record_id`),
    INDEX `idx_perishable_inventory_product_id` (`product_id`),
    INDEX `idx_perishable_inventory_date` (`date`),
    INDEX `idx_perishable_inventory_product_date` (`product_id`, `date`),
    CONSTRAINT `fk_perishable_inventory_product`
        FOREIGN KEY (`product_id`)
        REFERENCES `products` (`product_id`)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT `chk_perishable_inventory_opening_stock_non_negative` CHECK (`opening_stock` >= 0),
    CONSTRAINT `chk_perishable_inventory_units_received_non_negative` CHECK (`units_received` >= 0),
    CONSTRAINT `chk_perishable_inventory_units_sold_non_negative` CHECK (`units_sold` >= 0),
    CONSTRAINT `chk_perishable_inventory_discount_pct_range` CHECK (`discount_pct` >= 0 AND `discount_pct` <= 100),
    CONSTRAINT `chk_perishable_inventory_waste_units_non_negative` CHECK (`waste_units` >= 0),
    CONSTRAINT `chk_perishable_inventory_stockout_flag_binary` CHECK (`stockout_flag` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- -----------------------------------------------------
-- Table: discount_recommendations
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `discount_recommendations` (
    `recommendation_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `batch_id` INT UNSIGNED NOT NULL,
    `product_id` INT UNSIGNED NOT NULL,
    `days_to_expiry` INT NOT NULL,
    `quantity_remaining` INT UNSIGNED NOT NULL,
    `discount_pct` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    `predicted_gross_margin` DECIMAL(12,2) NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`recommendation_id`),
    UNIQUE INDEX `uq_discount_recommendations_batch` (`batch_id`),
    INDEX `idx_discount_recommendations_product_id` (`product_id`),
    INDEX `idx_discount_recommendations_days_to_expiry` (`days_to_expiry`),
    CONSTRAINT `fk_discount_recommendations_batch`
        FOREIGN KEY (`batch_id`)
        REFERENCES `inventory_batches` (`batch_id`)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT `fk_discount_recommendations_product`
        FOREIGN KEY (`product_id`)
        REFERENCES `products` (`product_id`)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT `chk_discount_recommendations_quantity_remaining_non_negative` CHECK (`quantity_remaining` >= 0),
    CONSTRAINT `chk_discount_recommendations_discount_pct_range` CHECK (`discount_pct` >= 0 AND `discount_pct` <= 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- -----------------------------------------------------
-- Table: calendar
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `calendar` (
    `date` DATE NOT NULL,
    `wm_yr_wk` INT UNSIGNED NOT NULL,
    `weekday` VARCHAR(15) NOT NULL,
    `wday` TINYINT UNSIGNED NOT NULL,
    `month` TINYINT UNSIGNED NOT NULL,
    `year` YEAR NOT NULL,
    `event_name_1` VARCHAR(50) DEFAULT NULL,
    `event_type_1` VARCHAR(50) DEFAULT NULL,
    `event_name_2` VARCHAR(50) DEFAULT NULL,
    `event_type_2` VARCHAR(50) DEFAULT NULL,
    `snap_CA` TINYINT(1) NOT NULL DEFAULT 0,
    `snap_TX` TINYINT(1) NOT NULL DEFAULT 0,
    `snap_WI` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`date`),
    INDEX `idx_calendar_wm_yr_wk` (`wm_yr_wk`),
    INDEX `idx_calendar_month_year` (`month`, `year`),
    CONSTRAINT `chk_calendar_wday_range` CHECK (`wday` BETWEEN 1 AND 7),
    CONSTRAINT `chk_calendar_month_range` CHECK (`month` BETWEEN 1 AND 12),
    CONSTRAINT `chk_calendar_snap_binary_ca` CHECK (`snap_CA` IN (0, 1)),
    CONSTRAINT `chk_calendar_snap_binary_tx` CHECK (`snap_TX` IN (0, 1)),
    CONSTRAINT `chk_calendar_snap_binary_wi` CHECK (`snap_WI` IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- -----------------------------------------------------
-- Table: forecast_results
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `forecast_results` (
    `forecast_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `product_id` INT UNSIGNED NOT NULL,
    `forecast_date` DATE NOT NULL,
    `target_date` DATE NOT NULL,
    `model_name` VARCHAR(50) NOT NULL,
    `predicted_waste_units` DECIMAL(10,2) DEFAULT NULL,
    `predicted_expiry_risk` DECIMAL(5,4) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`forecast_id`),
    INDEX `idx_forecast_results_product_id` (`product_id`),
    INDEX `idx_forecast_results_target_date` (`target_date`),
    INDEX `idx_forecast_results_model_name` (`model_name`),
    CONSTRAINT `fk_forecast_results_product`
        FOREIGN KEY (`product_id`)
        REFERENCES `products` (`product_id`)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT `chk_forecast_results_predicted_waste_non_negative` CHECK (`predicted_waste_units` IS NULL OR `predicted_waste_units` >= 0),
    CONSTRAINT `chk_forecast_results_predicted_expiry_risk_range` CHECK (`predicted_expiry_risk` IS NULL OR (`predicted_expiry_risk` >= 0 AND `predicted_expiry_risk` <= 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;