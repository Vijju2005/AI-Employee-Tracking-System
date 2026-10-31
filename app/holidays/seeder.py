"""
Idempotent Seeder for Karnataka Government Official Holidays (2026).
Can be called from bootstrap, startup routines, or executed standalone.
"""
from datetime import date
import logging
from app.extensions import db
from app.models import Holiday

logger = logging.getLogger("seed_holidays")

# Official Karnataka Government General Holidays for 2026
KARNATAKA_HOLIDAYS_2026 = [
    (date(2026, 1, 15), "Makara Sankranti", "Harvest festival celebrating the sun god"),
    (date(2026, 1, 26), "Republic Day", "National celebration of the Constitution of India"),
    (date(2026, 3, 19), "Ugadi Festival", "New Year's Day for Karnataka and Deccan region"),
    (date(2026, 3, 21), "Khutub-E-Ramzan", "Islamic holy festival of Eid-ul-Fitr"),
    (date(2026, 3, 31), "Mahaveera Jayanthi", "Celebration of the birth of Lord Mahavira"),
    (date(2026, 4, 3), "Good Friday", "Christian observance of the Crucifixion of Jesus Christ"),
    (date(2026, 4, 14), "Dr. B.R. Ambedkar Jayanthi", "Commemorating the father of the Indian Constitution"),
    (date(2026, 4, 20), "Basava Jayanthi, Akshaya Tritiya", "Birth anniversary of philosopher statesman Lord Basavanna and auspicious day of Akshaya Tritiya"),
    (date(2026, 5, 1), "May Day", "International Workers' Day"),
    (date(2026, 5, 28), "Bakrid", "Feast of the Sacrifice (Eid-al-Adha)"),
    (date(2026, 6, 26), "Last Day of Moharam", "Observance of the final day of Muharram"),
    (date(2026, 8, 15), "Independence Day", "National celebration of Indian Independence"),
    (date(2026, 8, 26), "Eid-Milad", "Commemoration of the birth of Prophet Muhammad"),
    (date(2026, 9, 14), "Varasiddhi Vinayaka Vrata", "Ganesh Chaturthi / worship of Lord Ganesha"),
    (date(2026, 10, 2), "Gandhi Jayanthi", "Birthday of Mahatma Gandhi, Father of the Nation"),
    (date(2026, 10, 20), "Mahanavami, Ayudhapooja", "Auspicious Navaratri ninth day and worship of tools and instruments"),
    (date(2026, 10, 21), "Vijayadasami", "Dussehra festival marking the victory of good over evil"),
    (date(2026, 11, 10), "Balipadyami, Deepavali", "Deepavali festival of lights celebrating the return of King Bali"),
    (date(2026, 11, 27), "Kanakadasa Jayanthi", "Birth anniversary of poet philosopher Bhakta Kanakadasa"),
    (date(2026, 12, 25), "Christmas", "Worldwide Christian celebration of the birth of Jesus Christ"),
]


def seed_karnataka_holidays_2026(session=None):
    """
    Idempotently seeds all 20 Karnataka Government 2026 holidays into the database.
    Does not duplicate existing dates or alter existing records.
    """
    s = session or db.session
    inserted_count = 0
    existing_count = 0

    for h_date, h_name, h_desc in KARNATAKA_HOLIDAYS_2026:
        existing = s.query(Holiday).filter_by(holiday_date=h_date).first()
        if not existing:
            new_holiday = Holiday(
                holiday_name=h_name,
                holiday_date=h_date,
                description=h_desc,
            )
            s.add(new_holiday)
            inserted_count += 1
        else:
            existing_count += 1

    try:
        s.commit()
        logger.info("Karnataka 2026 Holidays seeded: %d added, %d already present.", inserted_count, existing_count)
    except Exception as e:
        s.rollback()
        logger.error("Error committing Karnataka 2026 holidays: %s", e)
        raise e

    return inserted_count, existing_count
