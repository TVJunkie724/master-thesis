"""
AWS S3 Storage Cost Calculators
================================

Calculates AWS S3 storage costs for different tiers using the CS (Storage-Based) formula.

Storage Tiers:
    - S3 Infrequent Access (L3 Cool Storage)
    - S3 Glacier Deep Archive (L3 Archive Storage)

Each tier has different:
    - Storage price per GB-month
    - Write/request costs  
    - Data retrieval costs
"""

from typing import Dict, Any
from ..types import AWSComponent, FormulaType
from ...formulas import storage_based_cost, action_based_cost, required_first_unit_price


class AWSS3IACalculator:
    """
    AWS S3 Infrequent Access cost calculator for L3 Cool Storage.
    
    Uses: CS formula (storage-based) + CA formula (for write/retrieval)
    
    Pricing keys:
        - pricing["aws"]["s3InfrequentAccess"]["storagePrice"]
        - pricing["aws"]["s3InfrequentAccess"]["writePrice"]
        - pricing["aws"]["s3InfrequentAccess"]["dataRetrievalPrice"]
    """
    
    component_type = AWSComponent.S3_INFREQUENT_ACCESS
    formula_type = FormulaType.CS
    
    def calculate_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        retrievals_gb: float = 0.0
    ) -> float:
        """
        Calculate AWS S3 Infrequent Access monthly cost.
        
        Args:
            storage_gb: Storage volume in GB
            writes_per_month: Number of write operations (PUT/COPY)
            pricing: Full pricing dictionary
            retrievals_gb: Data retrieved in GB (for retrieval cost)
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["aws"]["s3InfrequentAccess"]
        
        # Storage cost (CS formula)
        storage_cost = storage_based_cost(
            price_per_gb_month=p["storagePrice"],
            volume_gb=storage_gb,
            duration_months=1.0
        )
        
        # Request meters are often billed in 1K/10K blocks; normalize at the
        # service boundary and never use hidden request-price defaults.
        write_price = required_first_unit_price(
            p,
            (
                ("writePrice", 1),
                ("requestPrice", 1),
                ("writePricePer1kRequests", 1_000),
                ("requestPricePer1kRequests", 1_000),
                ("writePricePer10kRequests", 10_000),
                ("requestPricePer10kRequests", 10_000),
            ),
            label="aws.s3InfrequentAccess.write",
        )
        write_cost = action_based_cost(
            price_per_action=write_price,
            num_actions=writes_per_month
        )
        
        # Retrieval cost (CA formula - price per GB retrieved)
        retrieval_price = 0.0
        if retrievals_gb > 0:
            retrieval_price = required_first_unit_price(
                p,
                (("dataRetrievalPrice", 1),),
                label="aws.s3InfrequentAccess.dataRetrieval",
            )
        retrieval_cost = action_based_cost(
            price_per_action=retrieval_price,
            num_actions=retrievals_gb
        )
        
        return storage_cost + write_cost + retrieval_cost


class AWSS3GlacierCalculator:
    """
    AWS S3 Glacier Deep Archive cost calculator for L3 Archive Storage.
    
    Uses: CS formula (storage-based) + CA formula (for write/lifecycle)
    
    Pricing keys:
        - pricing["aws"]["s3GlacierDeepArchive"]["storagePrice"]
        - pricing["aws"]["s3GlacierDeepArchive"]["writePrice"]
        - pricing["aws"]["s3GlacierDeepArchive"]["dataRetrievalPrice"]
        - pricing["aws"]["s3GlacierDeepArchive"]["lifecycleAndWritePrice"]
    """
    
    component_type = AWSComponent.S3_GLACIER_DEEP_ARCHIVE
    formula_type = FormulaType.CS
    
    def calculate_cost(
        self,
        storage_gb: float,
        writes_per_month: float,
        pricing: Dict[str, Any],
        retrievals_gb: float = 0.0
    ) -> float:
        """
        Calculate AWS S3 Glacier Deep Archive monthly cost.
        
        Args:
            storage_gb: Storage volume in GB
            writes_per_month: Number of write/lifecycle transitions
            pricing: Full pricing dictionary
            retrievals_gb: Data retrieved in GB (expensive for Glacier!)
            
        Returns:
            Monthly cost in USD
        """
        p = pricing["aws"]["s3GlacierDeepArchive"]
        
        # Storage cost (CS formula) - very cheap for Glacier
        storage_cost = storage_based_cost(
            price_per_gb_month=p["storagePrice"],
            volume_gb=storage_gb,
            duration_months=1.0
        )
        
        # Write/lifecycle cost (includes lifecycle transition cost)
        lifecycle_price = required_first_unit_price(
            p,
            (
                ("lifecycleAndWritePrice", 1),
                ("writePrice", 1),
                ("lifecycleAndWritePricePer1kRequests", 1_000),
                ("writePricePer1kRequests", 1_000),
                ("lifecycleAndWritePricePer10kRequests", 10_000),
                ("writePricePer10kRequests", 10_000),
            ),
            label="aws.s3GlacierDeepArchive.lifecycle",
        )
        write_cost = action_based_cost(
            price_per_action=lifecycle_price,
            num_actions=writes_per_month
        )
        
        # Retrieval cost - EXPENSIVE for Glacier!
        retrieval_price = 0.0
        if retrievals_gb > 0:
            retrieval_price = required_first_unit_price(
                p,
                (("dataRetrievalPrice", 1),),
                label="aws.s3GlacierDeepArchive.dataRetrieval",
            )
        retrieval_cost = action_based_cost(
            price_per_action=retrieval_price,
            num_actions=retrievals_gb
        )
        
        return storage_cost + write_cost + retrieval_cost
