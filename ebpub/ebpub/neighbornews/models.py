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

from django.contrib.gis.db import models
from ebpub.accounts.models import User
from ebpub.db.models import NewsItem

class NewsItemCreator(models.Model):
    """
    represents an add-on created-by relationship between
    a User and a NewsItem without interfering with the
    NewsItem model.
    """

    news_item = models.ForeignKey(NewsItem)
    user = models.ForeignKey(User)

    class Meta:
        unique_together = (('news_item', 'user'),)
        ordering = ('news_item',)
