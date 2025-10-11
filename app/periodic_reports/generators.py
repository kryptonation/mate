### app/periodic_reports/generators.py

# Standard library imports
from datetime import datetime, date, timedelta
from typing import Dict, Any, List

# Third party imports
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

# Local imports
from app.utils.logger import get_logger
from app.drivers.models import Driver
from app.medallions.models import Medallion
from app.vehicles.models import Vehicle
from app.leases.models import Lease
from app.pvb.models import PVBViolation
from app.ezpass.models import EZPassTransaction
from app.curb.models import CURBTrip
from app.bpm.models import Case, SLA
from app.ledger.models import DailyReceipt
from app.audit_trail.models import AuditTrail

logger = get_logger(__name__)


class BaseReportGenerator:
    """Base class for report generators"""
    
    def __init__(self):
        self.logger = logger
    
    def generate(self, db: Session, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate report data - to be implemented by subclasses"""
        raise NotImplementedError
    
    def _parse_date_parameter(self, date_str: str) -> date:
        """Parse date string parameter"""
        if isinstance(date_str, str):
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        return date_str
    
    def _get_date_range(self, parameters: Dict[str, Any]) -> tuple:
        """Get start and end dates from parameters"""
        start_date = parameters.get('start_date')
        end_date = parameters.get('end_date')
        
        if start_date:
            start_date = self._parse_date_parameter(start_date)
        else:
            # Default to last 30 days
            start_date = date.today() - timedelta(days=30)
        
        if end_date:
            end_date = self._parse_date_parameter(end_date)
        else:
            end_date = date.today()
        
        return start_date, end_date


class DriverSummaryGenerator(BaseReportGenerator):
    """Generator for driver summary reports"""
    
    def generate(self, db: Session, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            start_date, end_date = self._get_date_range(parameters)
            
            # Get driver statistics
            total_drivers = db.query(Driver).count()
            active_drivers = db.query(Driver).filter(Driver.driver_status == 'Active').count()
            inactive_drivers = db.query(Driver).filter(Driver.driver_status == 'Inactive').count()
            
            # New drivers in period
            new_drivers = db.query(Driver).filter(
                Driver.created_on >= start_date,
                Driver.created_on <= end_date
            ).all()
            
            # Driver status breakdown
            status_breakdown = db.query(
                Driver.driver_status,
                func.count(Driver.id).label('count')
            ).group_by(Driver.driver_status).all()
            
            # Recent driver activities (last 10)
            recent_drivers = db.query(Driver).order_by(Driver.created_on.desc()).limit(10).all()
            
            return {
                'summary': {
                    'total_drivers': total_drivers,
                    'active_drivers': active_drivers,
                    'inactive_drivers': inactive_drivers,
                    'new_drivers_in_period': len(new_drivers),
                    'period_start': start_date.isoformat(),
                    'period_end': end_date.isoformat()
                },
                'tables': {
                    'status_breakdown': [
                        {'status': status, 'count': count} for status, count in status_breakdown
                    ],
                    'new_drivers': [
                        {
                            'driver_id': driver.driver_id,
                            'name': f"{driver.first_name} {driver.last_name}",
                            'created_on': driver.created_on.isoformat() if driver.created_on else None,
                            'status': driver.driver_status
                        } for driver in new_drivers
                    ],
                    'recent_drivers': [
                        {
                            'driver_id': driver.driver_id,
                            'name': f"{driver.first_name} {driver.last_name}",
                            'status': driver.driver_status,
                            'created_on': driver.created_on.isoformat() if driver.created_on else None
                        } for driver in recent_drivers
                    ]
                }
            }
        except Exception as e:
            self.logger.error("Error generating driver summary report: %s", str(e), exc_info=True)
            raise


class MedallionStatusGenerator(BaseReportGenerator):
    """Generator for medallion status reports"""
    
    def generate(self, db: Session, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Get medallion statistics
            total_medallions = db.query(Medallion).count()
            
            # Medallion status breakdown
            status_breakdown = db.query(
                Medallion.medallion_status,
                func.count(Medallion.id).label('count')
            ).group_by(Medallion.medallion_status).all()
            
            # Recent medallion activities
            recent_medallions = db.query(Medallion).order_by(Medallion.updated_on.desc()).limit(20).all()
            
            return {
                'summary': {
                    'total_medallions': total_medallions,
                    'report_generated_on': datetime.utcnow().isoformat()
                },
                'tables': {
                    'status_breakdown': [
                        {'status': status or 'Unknown', 'count': count} for status, count in status_breakdown
                    ],
                    'recent_medallions': [
                        {
                            'medallion_number': medallion.medallion_number,
                            'status': medallion.medallion_status,
                            'owner': medallion.owner,
                            'updated_on': medallion.updated_on.isoformat() if medallion.updated_on else None
                        } for medallion in recent_medallions
                    ]
                }
            }
        except Exception as e:
            self.logger.error("Error generating medallion status report: %s", str(e), exc_info=True)
            raise


class VehicleInspectionGenerator(BaseReportGenerator):
    """Generator for vehicle inspection reports"""
    
    def generate(self, db: Session, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            start_date, end_date = self._get_date_range(parameters)
            
            # Get vehicle statistics
            total_vehicles = db.query(Vehicle).count()
            
            # Vehicles with upcoming inspections (next 30 days)
            upcoming_inspection_date = date.today() + timedelta(days=30)
            upcoming_inspections = db.query(Vehicle).filter(
                Vehicle.next_inspection_date <= upcoming_inspection_date,
                Vehicle.next_inspection_date >= date.today()
            ).all()
            
            # Recent vehicle activities
            recent_vehicles = db.query(Vehicle).order_by(Vehicle.updated_on.desc()).limit(20).all()
            
            return {
                'summary': {
                    'total_vehicles': total_vehicles,
                    'upcoming_inspections': len(upcoming_inspections),
                    'period_start': start_date.isoformat(),
                    'period_end': end_date.isoformat()
                },
                'tables': {
                    'upcoming_inspections': [
                        {
                            'plate_number': vehicle.plate_number,
                            'vin': vehicle.vin,
                            'next_inspection_date': vehicle.next_inspection_date.isoformat() if vehicle.next_inspection_date else None,
                            'vehicle_status': vehicle.vehicle_status
                        } for vehicle in upcoming_inspections
                    ],
                    'recent_vehicles': [
                        {
                            'plate_number': vehicle.plate_number,
                            'vin': vehicle.vin,
                            'status': vehicle.vehicle_status,
                            'updated_on': vehicle.updated_on.isoformat() if vehicle.updated_on else None
                        } for vehicle in recent_vehicles
                    ]
                }
            }
        except Exception as e:
            self.logger.error("Error generating vehicle inspection report: %s", str(e), exc_info=True)
            raise


class FinancialSummaryGenerator(BaseReportGenerator):
    """Generator for financial summary reports"""
    
    def generate(self, db: Session, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            start_date, end_date = self._get_date_range(parameters)
            
            # Basic financial metrics (placeholder - replace with actual financial models)
            return {
                'summary': {
                    'period_start': start_date.isoformat(),
                    'period_end': end_date.isoformat(),
                    'total_transactions': 0,  # Placeholder
                    'total_revenue': 0.0,     # Placeholder
                    'outstanding_amounts': 0.0  # Placeholder
                },
                'tables': {
                    'recent_transactions': [
                        # Placeholder data structure
                    ]
                }
            }
        except Exception as e:
            self.logger.error("Error generating financial summary report: %s", str(e), exc_info=True)
            raise


class LeaseExpiryGenerator(BaseReportGenerator):
    """Generator for lease expiry reports"""
    
    def generate(self, db: Session, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Leases expiring in next 30 days
            expiry_date = date.today() + timedelta(days=30)
            expiring_leases = db.query(Lease).filter(
                Lease.lease_end_date <= expiry_date,
                Lease.lease_end_date >= date.today()
            ).all()
            
            # Recently expired leases (last 30 days)
            recently_expired = db.query(Lease).filter(
                Lease.lease_end_date < date.today(),
                Lease.lease_end_date >= date.today() - timedelta(days=30)
            ).all()
            
            return {
                'summary': {
                    'expiring_soon': len(expiring_leases),
                    'recently_expired': len(recently_expired),
                    'report_date': date.today().isoformat()
                },
                'tables': {
                    'expiring_leases': [
                        {
                            'lease_id': lease.id,
                            'driver_name': f"{lease.driver.first_name} {lease.driver.last_name}" if lease.driver else "N/A",
                            'vehicle_plate': lease.vehicle.plate_number if lease.vehicle else "N/A",
                            'lease_end_date': lease.lease_end_date.isoformat() if lease.lease_end_date else None,
                            'days_to_expiry': (lease.lease_end_date - date.today()).days if lease.lease_end_date else None
                        } for lease in expiring_leases
                    ],
                    'recently_expired': [
                        {
                            'lease_id': lease.id,
                            'driver_name': f"{lease.driver.first_name} {lease.driver.last_name}" if lease.driver else "N/A",
                            'vehicle_plate': lease.vehicle.plate_number if lease.vehicle else "N/A",
                            'lease_end_date': lease.lease_end_date.isoformat() if lease.lease_end_date else None,
                            'days_expired': (date.today() - lease.lease_end_date).days if lease.lease_end_date else None
                        } for lease in recently_expired
                    ]
                }
            }
        except Exception as e:
            self.logger.error("Error generating lease expiry report: %s", str(e), exc_info=True)
            raise


class ViolationSummaryGenerator(BaseReportGenerator):
    """Generator for violation summary reports"""
    
    def generate(self, db: Session, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            start_date, end_date = self._get_date_range(parameters)
            
            # Get violation statistics
            total_violations = db.query(PVBViolation).filter(
                PVBViolation.created_on >= start_date,
                PVBViolation.created_on <= end_date
            ).count()
            
            # Recent violations
            recent_violations = db.query(PVBViolation).filter(
                PVBViolation.created_on >= start_date,
                PVBViolation.created_on <= end_date
            ).order_by(PVBViolation.created_on.desc()).limit(50).all()
            
            return {
                'summary': {
                    'total_violations': total_violations,
                    'period_start': start_date.isoformat(),
                    'period_end': end_date.isoformat()
                },
                'tables': {
                    'recent_violations': [
                        {
                            'ticket_number': violation.ticket_number,
                            'plate_number': violation.plate_number,
                            'violation_date': violation.violation_date.isoformat() if violation.violation_date else None,
                            'fine_amount': float(violation.fine_amount) if violation.fine_amount else 0.0,
                            'status': violation.status
                        } for violation in recent_violations
                    ]
                }
            }
        except Exception as e:
            self.logger.error("Error generating violation summary report: %s", str(e), exc_info=True)
            raise


class EZPassTransactionsGenerator(BaseReportGenerator):
    """Generator for EZPass transactions reports"""
    
    def generate(self, db: Session, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            start_date, end_date = self._get_date_range(parameters)
            
            # Get EZPass statistics
            total_transactions = db.query(EZPassTransaction).filter(
                EZPassTransaction.transaction_date >= start_date,
                EZPassTransaction.transaction_date <= end_date
            ).count()
            
            # Calculate total amount
            total_amount = db.query(func.sum(EZPassTransaction.amount)).filter(
                EZPassTransaction.transaction_date >= start_date,
                EZPassTransaction.transaction_date <= end_date
            ).scalar() or 0.0
            
            # Recent transactions
            recent_transactions = db.query(EZPassTransaction).filter(
                EZPassTransaction.transaction_date >= start_date,
                EZPassTransaction.transaction_date <= end_date
            ).order_by(EZPassTransaction.transaction_date.desc()).limit(100).all()
            
            return {
                'summary': {
                    'total_transactions': total_transactions,
                    'total_amount': float(total_amount),
                    'period_start': start_date.isoformat(),
                    'period_end': end_date.isoformat()
                },
                'tables': {
                    'recent_transactions': [
                        {
                            'transaction_date': txn.transaction_date.isoformat() if txn.transaction_date else None,
                            'plate_number': txn.plate_no,
                            'medallion_number': txn.medallion_no,
                            'amount': float(txn.amount) if txn.amount else 0.0,
                            'agency': txn.agency,
                            'status': txn.status
                        } for txn in recent_transactions
                    ]
                }
            }
        except Exception as e:
            self.logger.error("Error generating EZPass transactions report: %s", str(e), exc_info=True)
            raise


class TripAnalyticsGenerator(BaseReportGenerator):
    """Generator for trip analytics reports"""
    
    def generate(self, db: Session, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            start_date, end_date = self._get_date_range(parameters)
            
            # Get trip statistics
            total_trips = db.query(CURBTrip).filter(
                CURBTrip.start_date >= start_date,
                CURBTrip.start_date <= end_date
            ).count()
            
            # Recent trips
            recent_trips = db.query(CURBTrip).filter(
                CURBTrip.start_date >= start_date,
                CURBTrip.start_date <= end_date
            ).order_by(CURBTrip.start_date.desc()).limit(50).all()
            
            return {
                'summary': {
                    'total_trips': total_trips,
                    'period_start': start_date.isoformat(),
                    'period_end': end_date.isoformat()
                },
                'tables': {
                    'recent_trips': [
                        {
                            'trip_id': trip.id,
                            'driver_id': trip.driver_id,
                            'cab_number': trip.cab_number,
                            'start_date': trip.start_date.isoformat() if trip.start_date else None,
                            'end_date': trip.end_date.isoformat() if trip.end_date else None,
                            'fare': float(trip.fare) if trip.fare else 0.0
                        } for trip in recent_trips
                    ]
                }
            }
        except Exception as e:
            self.logger.error("Error generating trip analytics report: %s", str(e), exc_info=True)
            raise


class SLAPerformanceGenerator(BaseReportGenerator):
    """Generator for SLA performance reports"""
    
    def generate(self, db: Session, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            start_date, end_date = self._get_date_range(parameters)
            
            # Get SLA statistics
            total_cases = db.query(Case).filter(
                Case.created_on >= start_date,
                Case.created_on <= end_date
            ).count()
            
            # Recent cases
            recent_cases = db.query(Case).filter(
                Case.created_on >= start_date,
                Case.created_on <= end_date
            ).order_by(Case.created_on.desc()).limit(50).all()
            
            return {
                'summary': {
                    'total_cases': total_cases,
                    'period_start': start_date.isoformat(),
                    'period_end': end_date.isoformat()
                },
                'tables': {
                    'recent_cases': [
                        {
                            'case_no': case.case_no,
                            'case_type': case.case_type.name if case.case_type else "N/A",
                            'status': case.case_status.name if case.case_status else "N/A",
                            'created_on': case.created_on.isoformat() if case.created_on else None
                        } for case in recent_cases
                    ]
                }
            }
        except Exception as e:
            self.logger.error("Error generating SLA performance report: %s", str(e), exc_info=True)
            raise


class AuditTrailSummaryGenerator(BaseReportGenerator):
    """Generator for audit trail summary reports"""
    
    def generate(self, db: Session, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            start_date, end_date = self._get_date_range(parameters)
            
            # Get audit trail statistics
            total_activities = db.query(AuditTrail).filter(
                AuditTrail.created_on >= start_date,
                AuditTrail.created_on <= end_date
            ).count()
            
            # Recent activities
            recent_activities = db.query(AuditTrail).filter(
                AuditTrail.created_on >= start_date,
                AuditTrail.created_on <= end_date
            ).order_by(AuditTrail.created_on.desc()).limit(100).all()
            
            return {
                'summary': {
                    'total_activities': total_activities,
                    'period_start': start_date.isoformat(),
                    'period_end': end_date.isoformat()
                },
                'tables': {
                    'recent_activities': [
                        {
                            'activity_type': activity.audit_type.value if activity.audit_type else "N/A",
                            'description': activity.description,
                            'user': f"{activity.user.first_name} {activity.user.last_name}" if activity.user else "System",
                            'created_on': activity.created_on.isoformat() if activity.created_on else None
                        } for activity in recent_activities
                    ]
                }
            }
        except Exception as e:
            self.logger.error("Error generating audit trail summary report: %s", str(e), exc_info=True)
            raise


class PaymentSummaryGenerator(BaseReportGenerator):
    """
    Generator for comprehensive payment summary reports.
    """

    def generate(self, db: Session, parameters: Dict[str, Any]) -> Dict[str, Any]:
        try:
            start_date, end_date = self._get_date_range(parameters)

            # Step 1: Daily receipts summary
            daily_receipts_query = db.query(DailyReceipt).filter(
                DailyReceipt.created_on >= start_date,
                DailyReceipt.created_on <= end_date
            )

            daily_receipts = daily_receipts_query.all()
            total_daily_receipts = sum([r.balance for r in daily_receipts if r.balance])

            # Step 2: Ledger Entries (Credis and Debits)
            from app.ledger.models import LedgerEntry

            ledger_credits = db.query(LedgerEntry).filter(
                LedgerEntry.created_on >= start_date,
                LedgerEntry.created_on <= end_date,
                LedgerEntry.debit == False
            ).all()

            ledger_debits = db.query(LedgerEntry).filter(
                LedgerEntry.created_on >= start_date,
                LedgerEntry.created_on <= end_date,
                LedgerEntry.debit == True
            ).all()

            total_credits = sum([entry.amount for entry in ledger_credits if entry.amount])
            total_debits = sum([entry.amount for entry in ledger_debits if entry.amount])

            # 3. PVB Violation Payments
            pvb_payments = db.query(PVBViolation).filter(
                PVBViolation.created_on >= start_date,
                PVBViolation.created_on <= end_date,
                PVBViolation.status == 'Paid'
            )

            total_pvb_payments = sum([violation.fine_amount for violation in pvb_payments if violation.fine_amount])

            # 4. EZPass Transaction Amounts
            ezpass_transactions = db.query(EZPassTransaction).filter(
                EZPassTransaction.transaction_date >= start_date,
                EZPassTransaction.transaction_date <= end_date
            ).all()
            
            total_ezpass_amount = sum([t.amount for t in ezpass_transactions if t.amount])
            
            # 5. CURB Trip Revenue
            curb_revenue = db.query(CURBTrip).filter(
                CURBTrip.start_date >= start_date,
                CURBTrip.start_date <= end_date,
                CURBTrip.total_amount.isnot(None)
            ).all()
            
            total_curb_revenue = sum([t.total_amount for t in curb_revenue if t.total_amount])
            
            # 6. Lease Payment Analysis
            lease_schedules = db.query(LeaseSchedule).filter(
                LeaseSchedule.installment_due_date >= start_date,
                LeaseSchedule.installment_due_date <= end_date
            ).all()
            
            lease_payments_due = sum([ls.installment_amount for ls in lease_schedules if ls.installment_amount])
            lease_payments_paid = sum([ls.installment_amount for ls in lease_schedules 
                                     if ls.installment_amount and ls.installment_status == 'P'])
            
            # 7. Driver Payment Analysis
            driver_payments = []
            for receipt in daily_receipts:
                if receipt.driver:
                    driver_payments.append({
                        'driver_id': receipt.driver.driver_id,
                        'driver_name': f"{receipt.driver.first_name} {receipt.driver.last_name}",
                        'receipt_date': receipt.receipt_date.isoformat() if receipt.receipt_date else None,
                        'lease_amount': receipt.lease_amount or 0,
                        'gas_amount': receipt.gas_amount or 0,
                        'toll_amount': receipt.toll_amount or 0,
                        'total_amount': receipt.total_amount or 0,
                        'medallion_number': receipt.medallion.medallion_number if receipt.medallion else None
                    })
            
            # 8. Medallion Revenue Analysis
            medallion_summary = db.query(
                Medallion.medallion_number,
                func.sum(DailyReceipt.total_amount).label('total_revenue'),
                func.count(DailyReceipt.id).label('receipt_count')
            ).join(DailyReceipt).filter(
                DailyReceipt.receipt_date >= start_date,
                DailyReceipt.receipt_date <= end_date
            ).group_by(Medallion.medallion_number).all()
            
            medallion_revenue = [
                {
                    'medallion_number': m.medallion_number,
                    'total_revenue': float(m.total_revenue) if m.total_revenue else 0,
                    'receipt_count': m.receipt_count
                }
                for m in medallion_summary
            ]
            
            # 9. Outstanding Payments Analysis
            outstanding_pvb = db.query(PVBViolation).filter(
                or_(
                    PVBViolation.amount_paid.is_(None),
                    PVBViolation.amount_paid < PVBViolation.amount_due
                )
            ).all()
            
            total_outstanding_pvb = sum([
                (v.amount_due or 0) - (v.amount_paid or 0) 
                for v in outstanding_pvb if v.amount_due
            ])
            
            # 10. Payment Type Breakdown
            payment_types = db.query(
                DailyReceipt.payment_type,
                func.sum(DailyReceipt.total_amount).label('total'),
                func.count(DailyReceipt.id).label('count')
            ).filter(
                DailyReceipt.receipt_date >= start_date,
                DailyReceipt.receipt_date <= end_date
            ).group_by(DailyReceipt.payment_type).all()
            
            payment_type_breakdown = [
                {
                    'payment_type': pt.payment_type or 'Unknown',
                    'total_amount': float(pt.total) if pt.total else 0,
                    'transaction_count': pt.count
                }
                for pt in payment_types
            ]
            
            return {
                'summary': {
                    'period_start': start_date.isoformat(),
                    'period_end': end_date.isoformat(),
                    'total_daily_receipts': float(total_daily_receipts),
                    'total_credits': float(total_credits),
                    'total_debits': float(total_debits),
                    'net_ledger_amount': float(total_credits - total_debits),
                    'total_pvb_payments': float(total_pvb_payments),
                    'total_ezpass_amount': float(total_ezpass_amount),
                    'total_curb_revenue': float(total_curb_revenue),
                    'lease_payments_due': float(lease_payments_due),
                    'lease_payments_paid': float(lease_payments_paid),
                    'lease_payment_collection_rate': float(lease_payments_paid / lease_payments_due * 100) if lease_payments_due > 0 else 0,
                    'total_outstanding_pvb': float(total_outstanding_pvb),
                    'total_revenue': float(total_daily_receipts + total_curb_revenue),
                    'total_processed_payments': len(daily_receipts) + len(pvb_payments) + len(ezpass_transactions)
                },
                'tables': {
                    'driver_payments': driver_payments[:100],  # Limit for performance
                    'medallion_revenue': medallion_revenue,
                    'payment_type_breakdown': payment_type_breakdown,
                    'recent_ledger_credits': [
                        {
                            'date': entry.created_on.isoformat() if entry.created_on else None,
                            'amount': float(entry.amount) if entry.amount else 0,
                            'description': entry.description,
                            'driver_id': entry.driver_id,
                            'source_type': entry.source_type.name if hasattr(entry.source_type, 'name') else str(entry.source_type)
                        }
                        for entry in ledger_credits[:50]
                    ],
                    'recent_ledger_debits': [
                        {
                            'date': entry.created_on.isoformat() if entry.created_on else None,
                            'amount': float(entry.amount) if entry.amount else 0,
                            'description': entry.description,
                            'driver_id': entry.driver_id,
                            'source_type': entry.source_type.name if hasattr(entry.source_type, 'name') else str(entry.source_type)
                        }
                        for entry in ledger_debits[:50]
                    ],
                    'pvb_payments': [
                        {
                            'plate_number': v.plate_number,
                            'amount_due': float(v.amount_due) if v.amount_due else 0,
                            'amount_paid': float(v.amount_paid) if v.amount_paid else 0,
                            'issue_date': v.issue_date.isoformat() if v.issue_date else None,
                            'status': v.status
                        }
                        for v in pvb_payments[:50]
                    ],
                    'ezpass_transactions': [
                        {
                            'transaction_date': t.transaction_date.isoformat() if t.transaction_date else None,
                            'plate_number': t.plate_no,
                            'medallion_number': t.medallion_no,
                            'amount': float(t.amount) if t.amount else 0,
                            'agency': t.agency
                        }
                        for t in ezpass_transactions[:50]
                    ],
                    'lease_payment_status': [
                        {
                            'lease_id': ls.lease_id,
                            'installment_number': ls.installment_number,
                            'due_date': ls.installment_due_date.isoformat() if ls.installment_due_date else None,
                            'amount': float(ls.installment_amount) if ls.installment_amount else 0,
                            'status': ls.installment_status,
                            'paid_date': ls.installment_paid_date.isoformat() if ls.installment_paid_date else None
                        }
                        for ls in lease_schedules[:50]
                    ]
                }
            }
            
        except Exception as e:
            self.logger.error("Error generating payment summary report: %s", str(e), exc_info=True)
            raise

# Create generator instances
driver_summary_generator = DriverSummaryGenerator()
medallion_status_generator = MedallionStatusGenerator()
vehicle_inspection_generator = VehicleInspectionGenerator()
financial_summary_generator = FinancialSummaryGenerator()
lease_expiry_generator = LeaseExpiryGenerator()
violation_summary_generator = ViolationSummaryGenerator()
ezpass_transactions_generator = EZPassTransactionsGenerator()
trip_analytics_generator = TripAnalyticsGenerator()
sla_performance_generator = SLAPerformanceGenerator()
audit_trail_summary_generator = AuditTrailSummaryGenerator()
payment_summary_generator = PaymentSummaryGenerator()
