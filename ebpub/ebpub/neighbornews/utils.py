#   Copyright 2011 OpenPlans, and contributors
#
#   This file is part of ebpub
#
#   ebpub is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   ebpub is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with ebpub.  If not, see <http://www.gnu.org/licenses/>.
#

from django.http import HttpResponse
from ebpub.db.models import Schema
from ebpub.neighbornews.models import NewsItemCreator

NEIGHBOR_MESSAGE_SLUG = 'neighbor-messages'
NEIGHBOR_EVENT_SLUG = 'neighbor-events'

def app_enabled():
    from django.conf import settings
    return 'ebpub.neighbornews' in settings.INSTALLED_APPS

def is_schema_enabled(slug):
    try:
        return app_enabled() and Schema.objects.filter(slug=slug).values_list('is_public')[0][0]
    except IndexError:
        return False

def is_neighbor_message_enabled():
    return is_schema_enabled(NEIGHBOR_MESSAGE_SLUG)

def is_neighbor_event_enabled():
    return is_schema_enabled(NEIGHBOR_EVENT_SLUG)

def is_neighbornews_enabled():
    """
    check if the neighbornews schemas exist and are
    enabled.
    """
    return is_neighbor_message_enabled() or is_neighbor_event_enabled()

def if_disabled404(slug):
    """
    Decorator that checks whether the schema is disabled, and if so,
    the decorated view returns 404.
    """
    def decorator(func):
        def inner(*args, **kw):
            if not is_schema_enabled(slug):
                return HttpResponse(status=404)
            else:
                return func(*args, **kw)
        return inner
    return decorator

def user_can_edit(request, item):
    """Can the current user edit this NewsItem?
    """
    if request.user.is_anonymous():
        return False
    allowed = False
    if isinstance(item, basestring):
        item = int(item)
    if not isinstance(item, int):
        item = item.id
    if request.user.has_perm('db.change_newsitem'):
        allowed = True
    elif NewsItemCreator.objects.filter(news_item__id=item,
                                        user__id=request.user.id).count():
        allowed = True
    return allowed

def can_edit(func):
    """Decorator that checks whether you created this NewsItem, or
    have permission to edit all NewsItems.
    """
    def inner(request, newsitem, *args, **kw):
        if not user_can_edit(request, newsitem):
            return HttpResponse(status=403)
        return func(request, newsitem, *args, **kw)
    return inner
