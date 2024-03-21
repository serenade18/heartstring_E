import os

import django

from heartstringApp.models import Seat

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heartstringProject.settings')
django.setup()


def create_initial_seats():
    seat_layout = [
        {'wing': 'Left', 'seats': {'A': 3, 'B': 4, 'C': 5, 'D': 6, 'E': 7, 'F': 8, 'G': 0, 'H': 0, 'I': 0}},
        {'wing': 'Center', 'seats': {'A': 14, 'B': 15, 'C': 14, 'D': 15, 'E': 14, 'F': 15, 'G': 14, 'H': 15, 'I': 14}},
        {'wing': 'Right', 'seats': {'A': 3, 'B': 4, 'C': 5, 'D': 6, 'E': 7, 'F': 8, 'G': 0, 'H': 0, 'I': 0}},
    ]

    for layout in seat_layout:
        wing = layout['wing']
        seats_info = layout['seats']

        for row, cols in seats_info.items():
            for col in range(1, cols + 1):
                seat_id = f"{wing}-{row}{col}"
                seat = Seat(seat_id=seat_id, row=row, column=col, wing=wing)
                seat.save()

create_initial_seats()