# Copyright 2013 Rooter Analysis S.L.
# Copyright (c) 2013 Grupo Opentia
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

from moocng.mongodb import get_db
from moocng.assets import cache
from moocng.assets.models import Asset, AssetAvailability, Reservation
from moocng.courses.models import KnowledgeQuantum


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
