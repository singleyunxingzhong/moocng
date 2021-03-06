# Copyright 2013 UNED
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

import csv
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError

from pymongo import ASCENDING

from moocng.badges.models import Award
from moocng.courses.marks import calculate_course_mark
from moocng.courses.models import Course, KnowledgeQuantum
from moocng.mongodb import get_db


class Command(BaseCommand):

    help = ('Generate a csv file with one row per student with their stats on '
            'the given course')
    args = '<course_id_or_slug>'
    option_list = BaseCommand.option_list + (
        make_option(
            '--filename',
            dest='filename',
            default=None,
            help='Output filename.'
        ),
    )

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError('Wrong number of arguments')

        try:
            if args[0].isdigit():
                course = Course.objects.only('id', 'slug').get(id=args[0])
            else:
                course = Course.objects.only('id', 'slug').get(slug=args[0])
        except Course.DoesNotExist:
            raise CommandError('The course defined by "%s" does not exist' % args[0])

        filename = options.get('filename') or '%s.csv' % course.slug

        # Global stats (course level), repeated in every student
        units = course.unit_set.all().count()
        kqs = KnowledgeQuantum.objects.filter(unit__course__id=course.id).count()
        completed_first_unit = 0

        db = get_db()
        activity = db.get_collection('activity')
        rows = []
        badge = course.completion_badge

        for student in course.students.all():
            row = [
                student.username,
                student.get_full_name().encode('utf-8', 'ignore'),
                student.date_joined.isoformat(),
                course.id,
                units,
                kqs,
            ]

            course_act = activity.find(
                {
                    'course_id': course.id,
                    'user_id': student.id,
                },
                sort=[('_id', ASCENDING), ]
            )
            course_act_count = course_act.count()

            # Per students stats
            if course_act_count > 0:
                row.append(course_act[0]['_id'].generation_time.isoformat())
            else:
                row.append('N/A')

            progress = (course_act_count * 100) / kqs
            row.append(progress)

            completed_units = 0
            first = True
            for unit in course.unit_set.only('id').all():
                kqs_in_unit = unit.knowledgequantum_set.count()
                act = activity.find({
                    'user_id': student.id,
                    'unit_id': unit.id,
                }).count()
                if kqs_in_unit == act:
                    completed_units += 1
                if first:
                    first = False
                    completed_first_unit += completed_units
            row.append(completed_units)

            row.append(course_act_count)

            mark, _ = calculate_course_mark(course, student)
            row.append(mark)

            if badge:
                row.append(Award.objects.filter(badge=badge, user=student).exists())
            else:
                row.append('N/A')

            rows.append(row)

        with open(filename, 'wb') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'email',
                'full_name',
                'platform_date_joined',
                'course_id',
                'course_units',
                'course_nuggets',
                'first_activity_date',
                'progress_percentage',
                'completed_units',
                'completed_nuggets',
                'score',
                'got_completion_badge',
            ])
            writer.writerows(rows)
