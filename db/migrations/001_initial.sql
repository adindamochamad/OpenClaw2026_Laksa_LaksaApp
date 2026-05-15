CREATE DATABASE IF NOT EXISTS laksa_db CHARACTER SET utf8mb4;
USE laksa_db;

CREATE TABLE businesses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    owner_name VARCHAR(255),
    phone VARCHAR(20),
    business_type ENUM('warung', 'toko', 'jasa', 'kuliner', 'lainnya') DEFAULT 'warung',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    type ENUM('income', 'expense') NOT NULL,
    category VARCHAR(100),
    description TEXT,
    source ENUM('manual', 'doku', 'csv_upload') DEFAULT 'manual',
    doku_transaction_id VARCHAR(255),
    transaction_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id)
);

CREATE TABLE reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    report_type ENUM('daily', 'weekly', 'anomaly_alert') NOT NULL,
    period_start DATE,
    period_end DATE,
    health_score INT,
    total_income DECIMAL(15, 2),
    total_expense DECIMAL(15, 2),
    net_cashflow DECIMAL(15, 2),
    anomalies_detected JSON,
    recommendations TEXT,
    whatsapp_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id)
);

CREATE TABLE anomalies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    transaction_id INT,
    anomaly_type VARCHAR(100),
    severity ENUM('low', 'medium', 'high') DEFAULT 'medium',
    description TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);
