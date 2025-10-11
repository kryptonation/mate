## app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Settings for the application
    """

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False
    )

    pythonpath: str
    environment: str
    allowed_cors_urls: str

    redis_host: str
    redis_port: str
    redis_username: str
    redis_password: str

    db_host: str
    db_user: str
    db_password: str
    db_database: str
    db_port: int = 3360

    json_config: str = None

    bpm_file_key: str = None
    bat_file_key: str = None

    document_storage_dir: str = None
    allowed_file_types: str = None
    allowed_file_size: int = None

    aws_access_key_id: str = None
    aws_secret_access_key: str = None
    aws_region: str = None
    aws_sns_sender_id: str = None
    aws_ses_sender_email: str = None
    aws_ses_configuration_set: str = None
    s3_bucket_name: str = None

    claude_model_id: str = None

    app_base_url: str = None

    address_update_template_id: str = None
    storage_receipt_template_id: str = None
    dov_vehicle_lease_template_id: str = None
    medallion_lease_template_id: str = None
    driver_transaction_template_id: str = None
    royalty_agreement_corp_template_id: str = None
    royalty_agreement_llc_template_id: str = None
    royalty_agreement_individual_template_id: str = None
    rider_document_template_id: str = None
    medallion_cover_letter_template_id: str = None
    medallion_designation_template_id: str = None
    power_of_attorney_template_id: str = None

    curb_url: str = None
    curb_merchant: str = None
    curb_username: str = None
    curb_password: str = None

    secret_key: str = None
    algorithm: str = None
    access_token_expire_minutes: int = None
    refresh_token_expire_days: int = None

    vin_x_auth_key: str = ""
    firebase_cred_path: str = ""

    # Docusign integration
    docusign_client_id: str = None
    docusign_user_id: str = None
    docusign_account_id: str = None
    docusign_auth_server: str = "account-d.docusign.com"
    docusign_base_path: str = "https://demo.docusign.net/restapi"
    docusign_private_key_s3_key: str = None
    docusign_webhook_secret: str = None
    docusign_pem_path: str = None
    docusign_connect_webhook_url: str = None
    docusign_host_name: str = None
    docusign_host_email: str = None

    bat_manager_name: str = ""
    bat_authorized_agent: str = ""
    payment_date: str = ""
    security_deposit_holding_number: str = ""
    security_deposit_holding_bank: str = ""
    security_deposit_located_at: str = ""

    tlc_vehicle_cap_total: float = 0.00
    tlc_medallion_weekly_cap_regular: float = 0.00
    tlc_medallion_weekly_cap_hybrid: float = 0.00
    tlc_inspection_fees: float = 0.00
    tax_stamps: float = 0.00
    registration: float = 0.00

    common_date_format: str = ""
    common_signature_file: str = ""

    dov_security_deposit_cap: float = 0.00
    long_term_medallion_weekly_cap_medallion_regular: float = 0.00
    long_term_medallion_weekly_cap_medallion_hybrid: float = 0.00

    @property
    def db_url(self) -> str:
        """
        Sync database URL
        """
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_database}"

    @property
    def async_db_url(self) -> str:
        """
        Async database URL
        """
        return f"mysql+asyncmy://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_database}"

    @property
    def redis_url(self) -> str:
        """
        Redis connection URL
        """
        if self.redis_username and self.redis_password:
            return f"redis://{self.redis_username}:{self.redis_password}@{self.redis_host}:{self.redis_port}"
        elif self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}"

    @property
    def cache_manager(self) -> str:
        """
        Cache manager type
        """
        return f"{self.redis_url}/0"

    @property
    def celery_broker(self) -> str:
        """
        Celery broker URL
        """
        return f"{self.redis_url}/1"

    @property
    def celery_backend(self) -> str:
        """
        Celery backend URL
        """
        return f"{self.redis_url}/2"


settings = Settings()
