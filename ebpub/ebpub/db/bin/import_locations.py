#!/usr/bin/env python
#   Copyright 2007,2008,2009,2011 Everyblock LLC, OpenPlans, and contributors
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

import os
import sys
import datetime
from optparse import OptionParser
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import Polygon
from django.db import connection
from django.db.utils import IntegrityError
from ebpub.db.models import Location, LocationType, NewsItem
from ebpub.geocoder.parser.parsing import normalize
from ebpub.utils.text import slugify
from ebpub.metros.allmetros import get_metro

def populate_ni_loc(location):
    """
    Add NewsItemLocations for all NewsItems that overlap with the new
    Location.
    """
    ni_count = NewsItem.objects.count()
    cursor = connection.cursor()
    i = 0
    while i < ni_count:
        cursor.execute("""
            INSERT INTO db_newsitemlocation (news_item_id, location_id)
            SELECT ni.id, loc.id FROM db_newsitem ni, db_location loc
            WHERE intersecting_collection(ni.location, loc.location)
                AND ni.id >= %s AND ni.id < %s
                AND loc.id = %s
        """, (i, i+200, location.id))
        connection._commit()
        i += 200

class LocationImporter(object):
    def __init__(self, layer, location_type, opts):
        self.layer = layer
        metro = get_metro()
        self.metro_name = metro['metro_name'].upper()
        self.now = datetime.datetime.now()
        self.location_type = location_type
        self.opts = opts
        if self.opts.filter_bounds:
            self.bounds = Polygon.from_bbox(metro['extent'])

    def save(self):
        verbose = self.opts.verbose
        name_field = self.opts.name_field
        source = self.opts.source
        locs = []
        for feature in self.layer:
            name = feature.get(name_field)
            geom = feature.geom.transform(4326, True).geos
            if not geom.valid:
                geom = geom.buffer(0.0)
                if not geom.valid:
                    print >> sys.stderr, 'Warning: invalid geometry: %s' % name
            fields = dict(
                name = name,
                normalized_name = normalize(name),
                slug = slugify(name),
                location_type = self.get_location_type(feature),
                location = geom,
                centroid = geom.centroid,
                city = self.metro_name,
                source = source,
                area = geom.transform(3395, True).area,
                is_public = True,
                display_order = 0, # This is overwritten in the next loop
            )
            if not self.should_create_location(fields):
                continue
            locs.append(fields)
        num_created = 0
        for i, loc_fields in enumerate(sorted(locs, key=lambda h: h['name'])):
            kwargs = dict(loc_fields, defaults={'creation_date': self.now, 'last_mod_date': self.now, 'display_order': i})
            try:
                loc, created = Location.objects.get_or_create(**kwargs)
            except IntegrityError:
                # Usually this means two towns with the same slug.
                # Try to fix that.
                slug = kwargs['slug']
                existing = Location.objects.filter(slug=slug).count()
                if existing:
                    slug = slugify('%s-%s' % (slug, existing + 1))
                    if verbose:
                        print >> sys.stderr, "Munged slug %s to %s to make it unique" % (kwargs['slug'], slug)
                    kwargs['slug'] = slug
                    loc, created = Location.objects.get_or_create(**kwargs)
                else:
                    raise
            if created:
                num_created += 1
            if verbose:
                print >> sys.stderr, '%s %s %s' % (created and 'Created' or 'Already had', self.location_type.name, loc)
            if verbose:
                sys.stderr.write('Populating newsitem locations ... ')
            populate_ni_loc(loc)
            if verbose:
                sys.stderr.write('done.\n')
        return num_created

    def should_create_location(self, fields):
        if self.opts.filter_bounds:
            if not fields['location'].intersects(self.bounds):
                if self.opts.verbose:
                    print >> sys.stderr, "Skipping %s, out of bounds" % fields['name']
                return False
        return True

    def get_location_type(self, feature):
        return self.location_type

usage = 'usage: %prog [options] type_slug /path/to/shapefile'

optparser = OptionParser(usage=usage)
optparser.add_option('-n', '--name-field', dest='name_field', default='name', help='field that contains location\'s name')
optparser.add_option('-i', '--layer-index', dest='layer_id', default=0, help='index of layer in shapefile')
optparser.add_option('-s', '--source', dest='source', default='UNKNOWN', help='source metadata of the shapefile')
optparser.add_option('-v', '--verbose',  action='store_true', default=False, help='be verbose')
optparser.add_option('-b', '--filter-bounds', action='store_true', default=False,
                     help="exclude locations not within the lon/lat bounds of "
                     " your metro's extent (from your settings.py) (default false)")

def parse_args(optparser, argv):
    # Add some options that aren't relevant to scripts that import our optparser.
    optparser.add_option('--type-name', dest='type_name', default='', help='specifies the location type name')
    optparser.add_option('--type-name-plural', dest='type_name_plural', default='', help='specifies the location type plural name')
    opts, args = optparser.parse_args(argv)

    if len(args) != 2:
        optparser.error('must supply type slug and path to shapefile')
    type_slug = args[0]
    shapefile = args[1]

    return opts

def main():
    opts = parse_args(optparser, sys.argv[1:])

    if not os.path.exists(shapefile):
        optparser().error('file does not exist')
    ds = DataSource(shapefile)
    layer = ds[opts.layer_id]

    metro = get_metro()
    metro_name = metro['metro_name'].upper()
    try:
        location_type = LocationType.objects.get(slug = type_slug)
        if opts.verbose:
            print >> sys.stderr, "Location type %s already exists, ignoring type-name and type-name-plural" % type_slug
    except LocationType.DoesNotExist:
        location_type, _ = LocationType.objects.get_or_create(
            name = opts.type_name,
            plural_name = opts.type_name_plural,
            scope = metro_name,
            slug = type_slug,
            is_browsable = True,
            is_significant = True,
            )
    importer = LocationImporter(layer, location_type, opts)
    num_created = importer.save()
    if opts.verbose:
        print >> sys.stderr, 'Created %s %s.' % (num_created, location_type.plural_name)

if __name__ == '__main__':
    sys.exit(main())
