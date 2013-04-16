# Copyright 2013 Rooter Analysis S.L.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import datetime

from django.db import IntegrityError
from django.db.models import Q
from django.utils.translation import ugettext as _

from moocng.mongodb import get_db
from moocng.assets import cache
from moocng.assets.models import Asset, AssetAvailability, Reservation
from moocng.courses.models import KnowledgeQuantum, Course


def course_get_assets(course):
    return Asset.objects.filter(available_in__kq__unit__course__id=course.id)


def course_get_kq_with_bookable_assets(course):
    kq_ids = AssetAvailability.objects.filter(kq__unit__course__id=course.id).values_list('kq', flat=True)
    return KnowledgeQuantum.objects.filter(id__in=kq_ids)


def course_has_assets(course):
    result = cache.get_course_has_assets_from_cache(course)
    if result is None:
        assets = course_get_assets(course)
        result = assets.count() > 0
        cache.set_course_has_assets_in_cache(course, result)
    return result


def user_course_get_reservations(user, course):
    return Reservation.objects.filter(Q(reserved_from__kq__unit__course__id=course.id)
                                      & Q(user__id=user.id))


def user_course_get_active_reservations(user, course, time=None):
    if time is None:
        time = datetime.datetime.now()
    result = user_course_get_reservations(user, course).filter(Q(reservation_begins__lte=time)
                                                               & Q(reservation_ends__gte=time))
    return result


def user_course_get_past_reservations(user, course, time=None):
    if time is None:
        time = datetime.datetime.now()
    result = user_course_get_reservations(user, course).filter(reservation_ends__lt=time).order_by('-reservation_begins')
    return result


def user_course_get_pending_reservations(user, course, time=None):
    if time is None:
        time = datetime.datetime.now()
    result = user_course_get_reservations(user, course).filter(Q(reservation_begins__gt=time)
                                                               & Q(reservation_ends__gt=time)).order_by('reservation_begins')
    return result


def is_asset_bookable(user, asset, availability, reservation_begins, reservation_ends):
    """This method checks if there is possible to create a new reservation
    with the given parameters.
    It returns a tuple whose first parameter is a boolean which specifies if
    it's possible to create the reservation, and if it's not possible the
    second parameter would be a string which specifies why it's not possible
    to create the reservation"""

    if not availability.assets.filter(id=asset.id).exists():
        return(False, _('This asset is not available from this nugget.'))

    if reservation_begins > reservation_ends:
        return(False, _('A reservation should not finish before it starts.'))

    reservation_limit = datetime.datetime.today()
    reservation_limit += datetime.timedelta(0, asset.reservation_in_advance * 60)

    if reservation_begins < datetime.datetime.today():
        return (False, _('The specified time is in the past.'))
    if reservation_begins < reservation_limit:
        return (False, _('Not enought time in advance for this reservation'))
    if reservation_begins.date() < availability.available_from or reservation_ends.date() > availability.available_to:
        return (False, _('The specified time is not in the bookable period.'))

    course = availability.kq.unit.course
    if user_course_get_pending_reservations(user, course).count() >= course.max_reservations_pending:
        return (False, _('You have reached the pending reservations limit for this course.'))
    elif user_course_get_reservations(user, course).count() >= course.max_reservations_total:
        return (False, _('You have reached the reservations limit for this course.'))

    collisions = Reservation.objects.filter(asset__id=asset.id)
    collisions = collisions.exclude(Q(reservation_begins__gt=reservation_begins)
                                    | Q(reservation_ends__lt=reservation_ends))
    if (collisions.count() >= asset.max_bookable_slots):
        return (False, _("There's not a free slot available."))

    return (True, None)

def book_asset(user, asset, availability, reservation_begins, reservation_ends):
    """This method checks if there is possible to create a new reservation
    with the given parameters, and if it's possible it creates the reservation.
    It returns a tuple whose first parameter is a boolean which specifies if
    the reservation was created, and the second element is a message specifying
    that the reservation was created or the reason why it couldn't be created.
    """
    can_create = is_asset_bookable(user, asset, availability, reservation_begins, reservation_ends)
    if not can_create[0]:
        return can_create

    collisions = Reservation.objects.filter(asset__id=asset.id)
    collisions = collisions.exclude(Q(reservation_begins__gt=reservation_ends)
                                    | Q(reservation_ends__lt=reservation_begins))
    used_slots = collisions.values_list('slot_id', flat=True)

    free_slots = range(asset.max_bookable_slots)

    for i in used_slots:
        try:
            free_slots.remove(i)
        except ValueError:
            pass
    if len(free_slots) == 0:
        return (False, _("There's not a free slot available."))

    slot = free_slots[0]

    new_reservation = Reservation(user=user, asset=asset, slot_id = slot,
                                  reserved_from=availability,
                                  reservation_begins=reservation_begins,
                                  reservation_ends=reservation_ends)

    new_reservation.save();

    return (True, _("Reservation created successfully."));
