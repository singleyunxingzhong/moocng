# -*- coding: utf-8 -*-
# Copyright 2012-2013 UNED
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

from datetime import date

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _


from moocng.courses.models import Course, Unit, CourseTeacher
from moocng.http import Http410


def can_user_view_course(course, user):

    """
    Returns a pair where the first element is a bool indicating if the user
    can view the course and the second one is a string code explaining the
    reason.

    :returns: Bool

    .. versionadded:: 0.1
    """
    if course.is_active:
        return True, 'active'

    if user.is_superuser:
        return True, 'is_superuser'

    if user.is_staff:
        return True, 'is_staff'

    # check if the user is a teacher of the course
    if not user.is_anonymous():
        try:
            CourseTeacher.objects.get(teacher=user, course=course)
            return True, 'is_teacher'
        except CourseTeacher.DoesNotExist:
            pass

    # at this point you don't have permissions to see a course
    if course.is_public:
        return False, 'not_active_outdated'
    return False, 'not_active_yet'


def check_user_can_view_course(course, request):

    """
    Raises a 404 error if the user can't see the course.

    :returns: message or 404

    .. versionadded:: 0.1
    """
    can_view, reason = can_user_view_course(course, request.user)

    if can_view:
        if reason != 'active':
            msg_table = {
                'is_staff': _(u'This course is not public. Your have access to it because you are staff member'),
                'is_superuser': _(u'This course is not public. Your have access to it because you are a super user'),
                'is_teacher': _(u'This course is not public. Your have access to it because you are a teacher of the course'),
            }
            messages.warning(request, msg_table[reason])
    else:
        if reason == 'not_active_yet':
            raise Http404()
        else:
            user = request.user
            msg = _("We're sorry, but the course has finished. ")
            if not user.is_anonymous():
                msg += _("You could see your transcript <a href=\"%s\">here</a>") % reverse('transcript', args=(course.slug,))
            raise Http410(msg)


def get_course_if_user_can_view_or_404(course_slug, request):
    course = get_object_or_404(Course, slug=course_slug)
    check_user_can_view_course(course, request)
    return course


def get_courses_available_for_user(user):

    """
    Filter in a list of courses what courses are available for the user.

    :returns: Object list

    .. versionadded:: 0.1
    """
    if user.is_superuser or user.is_staff:
        # Return every course that hasn't finished
        return Course.objects.exclude(end_date__lt=date.today())
    elif user.is_anonymous() or not CourseTeacher.objects.filter(teacher=user).exists():
        # Regular user, return only the published courses
        return Course.objects.exclude(end_date__lt=date.today()).filter(status='p')
    else:
        # Is a teacher, return draft courses if he is one of its teachers
        return Course.objects.exclude(end_date__lt=date.today()).filter(Q(status='p') | Q(status='d', courseteacher__teacher=user)).distinct()


def get_units_available_for_user(course, user, is_overview=False):

    """
    Filter units of a course what courses are available for the user.

    :returns: Object list

    .. versionadded:: 0.1
    """
    if user.is_superuser or user.is_staff:
        return course.unit_set.all()
    elif user.is_anonymous():
        if is_overview:
            return course.unit_set.filter(Q(status='p') | Q(status='l'))
        else:
            return []
    else:
        if is_overview:
            return Unit.objects.filter(
                Q(status='p', course=course) |
                Q(status='l', course=course) |
                Q(status='d', course=course, course__courseteacher__teacher=user, course__courseteacher__course=course)).distinct()
        else:
            return Unit.objects.filter(
                Q(status='p', course=course) |
                Q(status='l', course=course, course__courseteacher__teacher=user, course__courseteacher__course=course) |
                Q(status='d', course=course, course__courseteacher__teacher=user, course__courseteacher__course=course)).distinct()
