"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

import base64
import json
from django.test import TestCase
from django.test.client import Client

from piston.utils import rc
from mlscommon.entrytypes import *
from api.handlers import CellHandler

from piston.decorator import decorator


# TODO mongoengine errors should be fixed
import warnings
warnings.filterwarnings("ignore")


class AuthTestCase(TestCase):
    # def _pre_setup(self):
    #     print "Hi _pre_setup"
    #     super(TestCase, self)._pre_setup()

    # def __init__(self):
    #     from pymongo.connection import Connection
    #     self.connection = Connection()
    #     self.db = connection['melisi-example']

    #     super(AuthTestCase, self).__init__()

    def _dropdb(self):
        self.connection.drop_database("melisi-example")

    def _fixture_setup(self):
        self.teardown(full=True)

    def _fixture_teardown(self):
        pass

    def teardown(self, full=False):
        if full:
            map(lambda x: x.delete(), Cell.objects.all())
            map(lambda x: x.delete(), User.objects.all())
        else:
            map(lambda x: x.delete(), Cell.objects.filter(name__ne = 'melissi'))

    def auth(self, username, password):
        auth = '%s:%s' % (username, password)
        auth = 'Basic %s' % base64.encodestring(auth)
        auth = auth.strip()

        extra = {'HTTP_AUTHORIZATION' : auth}

        return extra

    def create_superuser(self):
        user = { 'username': 'admin',
                 'password': '123',
                 'email': 'admin@example.com',
                 }
        user['auth'] = self.auth(user['username'], user['password'])

        try:
            u = MelissiUser.create_user(user['username'], user['email'], user['password'])
            u.is_superuser = True
            u.is_staff = True
            u.save()
        except OperationError:
            pass

        return user

    def create_user(self, username='melisi', email='melisi@example.com'):
        user = { 'username': username,
                 'password': '123',
                 'email': email,
                 }
        user['auth'] = self.auth(user['username'], user['password'])

        try:
            MelissiUser.create_user(user['username'], user['email'], user['password'])
        except OperationError:
            pass

        return user


    def create_anonymous(self):
        user = {'auth': {}}
        return user

@decorator
def test_multiple_users(function, self, *args, **kwargs):
    dic = function(self, *args, **kwargs)
    # Test
    for user, data in dic['users'].iteritems():
        # print "Testing", user
        s = {}
        if dic.get('setup'):
            s = dic['setup']() or {}

        method = getattr(self.client, dic['method'])

        postdata = {}
        for key, value in dic.get('postdata', {}).iteritems():
            if isinstance(dic['postdata'][key], basestring):
                postdata[key] = value % s
            else:
                postdata[key] = value

        response = method(dic['url'] % s,
                          postdata,
                          **data['auth'])

        # print response.content

        self.assertEqual(response.status_code, dic['response_code'][user])

        if response.status_code == 200 and 'content' in dic:
            self.assertContains(response, dic['content'] % s)

        if dic.get('checks') and dic['checks'].get(user):
            dic['checks'][user](response)

        if dic.get('teardown'):
            dic['teardown']()


class UserTest(AuthTestCase):
    def setUp(self):
        self.username = 'testuser'
        self.password = '123'
        self.email = 'testuser@example.com'

        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': { 'username' : self.username,
                       'password' : self.password,
                       'email' : self.email,
                       'auth' : self.auth(self.username, self.password)
                       }
            }

    @test_multiple_users
    def test_create_user(self):
        def teardown():
            User.objects(username='testuser').delete()

        users = self.users.copy()
        users.pop('owner')
        dic = {
            'teardown': teardown,
            'response_code': {'user': 401,
                              'admin': 200,
                              'anonymous':200,
                              },
            'postdata': {'username':'testuser',
                         'password':'123',
                         'password2':'123',
                         'email':'foo@example.com'
                         },
            'method':'post',
            'url': '/api/user/',
            'users': users
            }
        return dic

    @test_multiple_users
    def test_create_user_denied_password_verify(self):
        def teardown():
            User.objects(username='testuser').delete()

        users = self.users.copy()
        users.pop('owner')
        dic = {
            'teardown': teardown,
            'response_code': {'user': 400,
                              'admin': 400,
                              'anonymous':400,
                              },
            'postdata': {'username':'testuser',
                         'password':'123',
                         'password2':'124',
                         'email':'foo@example.com'
                         },
            'method':'post',
            'url': '/api/user/',
            'users': users
            }
        return dic

    @test_multiple_users
    def test_get_user(self):
        # Prepare
        MelissiUser.create_user(self.username, self.email, self.password)

        dic = {
            'response_code': {'user': 401,
                              'admin': 200,
                              'anonymous':401,
                              'owner': 200,
                              },
            'method':'get',
            'url': '/api/user/testuser/',
            'users': self.users
            }
        return dic

    @test_multiple_users
    def test_update_user(self):
        # Prepare
        def setup():
            MelissiUser.create_user(self.username, self.email, self.password)

        def teardown():
            User.objects(username=self.username).delete()
            User.objects(username='usertest').delete()

        # Test
        dic = {
            'setup': setup,
            'teardown': teardown,
            'response_code': {'user': 401,
                              'admin': 200,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {'username':'usertest',
                         'password':'123'
                         },
            'content': 'usertest',
            'method':'put',
            'url': '/api/user/testuser/',
            'users': self.users
            }

        return dic

    @test_multiple_users
    def test_delete_user(self):
        # Prepare
        def setup():
            MelissiUser.create_user(self.username, self.email, self.password)

        def teardown():
            User.objects(username=self.username).delete()

        dic = {
            'setup': setup,
            'teardown': teardown,
            'response_code': {'user': 401,
                              'admin': 204,
                              'anonymous':401,
                              'owner': 204,
                              },
            'method':'delete',
            'url': '/api/user/testuser/',
            'users': self.users
            }
        return dic


class CellTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com")
            }

    @test_multiple_users
    def test_create_root_cell(self):
        dic = {
            'teardown': self.teardown,
            'response_code': {'user': 200,
                              'admin': 200,
                              'anonymous':401,
                              'owner': 200,
                              },
            'postdata': {
                'name':'test',
                },
            'content': 'test',
            'method':'post',
            'url': '/api/cell/',
            'users': self.users
            }

        return dic

    @test_multiple_users
    def test_create_child_cell(self):
        # Prepare
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="foo", revisions=[CellRevision(name="foo", resource=ur)], owner=u)
            c.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous':401,
                              'owner':200,
                              },
            'postdata': {
                'name':'test',
                'parent':'%(cell_id)s',
                },
            'content': 'test',
            'method':'post',
            'url': '/api/cell/',
            'users': self.users
            }

        return dic


    @test_multiple_users
    def test_read_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="foo", revisions=[CellRevision(name="foo", resource=ur)], owner=u)
            c.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup':setup,
            'teardown':self.teardown,
            'method':'get',
            'url':'/api/cell/%(cell_id)s/',
            'users': self.users,
            'content': '%(cell_id)s',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }
        return dic

    @test_multiple_users
    def test_update_name_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="foo", revisions=[CellRevision(name="foo", resource=ur)], owner=u)
            c.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup':setup,
            'teardown':self.teardown,
            'method':'put',
            'url':'/api/cell/%(cell_id)s/',
            'users': self.users,
            'postdata': { 'name': 'bar', 'number': 1 },
            'content': 'bar',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }
        return dic

    @test_multiple_users
    def test_denied_update_name_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="foo", revisions=[CellRevision(name="foo", resource=ur)], owner=u)
            c.save()
            c1 = Cell(name="bar", revisions=[CellRevision(name="bar", resource=ur)], owner=u)
            c1.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup':setup,
            'teardown':self.teardown,
            'method':'put',
            'url':'/api/cell/%(cell_id)s/',
            'users': self.users,
            'postdata': { 'name': 'bar' },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 400,
                              }
            }
        return dic


    @test_multiple_users
    def test_move_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c1 = Cell(name="foo", revisions=[CellRevision(name="foo", resource=ur)], owner=u)
            c1.save()

            c2 = Cell(name="bar", revisions=[CellRevision(name="bar", resource=ur)], owner=u, roots=[c1])
            c2.save()

            c3 = Cell(name="new-root", revisions=[CellRevision(name="new-root", resource=ur)], owner=u)
            c3.save()

            c4 = Cell(name="child-bar", revisions=[CellRevision(name="child-bar", resource=ur)], owner=u, roots=[c2,c1])
            c4.save()

            return { 'c2': c2.pk, 'c3': c3.pk }

        def extra_checks(response):
            # do more detailed tests
            c2 = Cell.objects.get(name="bar")
            c4 = Cell.objects.get(name="child-bar")
            c3 = Cell.objects.get(name="new-root")

            self.assertEqual(c2.roots, [c3])
            self.assertEqual(c4.roots, [c2,c3])


        dic = {
            'setup':setup,
            'teardown':self.teardown,
            'method':'put',
            'url':'/api/cell/%(c2)s/',
            'users': self.users,
            'postdata': { 'parent': '%(c3)s', 'number': 1 },
            'content': '%(c3)s',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              },
            'checks' : { 'owner': extra_checks }
            }
        return dic

    @test_multiple_users
    def test_denied_move_cell(self):
        """ Try to move a cell into another cell without permission """
        def setup():
            u1 = User.objects.get(username="foo")
            u2 = User.objects.get(username="melisi")
            ur1 = UserResource.objects.get(user=u1)
            ur2 = UserResource.objects.get(user=u2)
            c1 = Cell(name="foo", revisions=[CellRevision(name="foo", resource=ur1)], owner=u1)
            c1.save()

            c2 = Cell(name="bar", revisions=[CellRevision(name="bar", resource=ur1)], owner=u1, roots=[c1])
            c2.save()

            c3 = Cell(name="bar", revisions=[CellRevision(name="bar", resource=ur2)], owner=u2)
            c3.save()

            c4 = Cell(name="child-bar", revisions=[CellRevision(name="child-bar", resource=ur1)], owner=u1, roots=[c2,c1])
            c4.save()

            return { 'c2': c2.pk, 'c3': c3.pk }

        dic = {
            'setup':setup,
            'teardown':self.teardown,
            'method':'put',
            'url':'/api/cell/%(c2)s/',
            'users': self.users,
            'postdata': { 'parent': '%(c3)s' },
            'content': '%(c3)s',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 401,
                              },
            }
        return dic

    @test_multiple_users
    def test_delete_cascade(self):
        """ Delete a cell and check that all children cells and
        droplets have been deleted """

        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c1 = Cell(name="root", revisions=[CellRevision(name="root", resource=ur)], owner=u)
            c1.save()
            c2 = Cell(name="child1", revisions=[CellRevision(name="child1", resource=ur)], owner=u, roots=[c1])
            c2.save()
            c3 = Cell(name="child2", revisions=[CellRevision(name="child2", resource=ur)], owner=u, roots=[c2,c1])
            c3.save()
            d1 = Droplet(name="drop1", owner=u, cell=c1, revisions=[DropletRevision(name="drop1", resource=ur)])
            d1.save()
            d2 = Droplet(name="drop2", owner=u, cell=c3, revisions=[DropletRevision(name="drop2", resource=ur)])
            d2.save()
            return { 'cell_id': c1 }

        def extra_checks(response):
            self.assertEqual(Cell.objects(deleted=True).count(), 3)
            self.assertEqual(Droplet.objects(deleted=True).count(), 2)

        dic = {
            'setup':setup,
            'teardown':self.teardown,
            'method':'delete',
            'url':'/api/cell/%(cell_id)s/',
            'users':self.users,
            'response_code': {'user': 401,
                              'admin':401,
                              'owner':204,
                              'anonymous':401
                              },
            'checks':{'owner':extra_checks}
            }

        return dic

    @test_multiple_users
    def test_delete_cell(self):
        # Prepare
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="foo", revisions=[CellRevision(name="foo", resource=ur)], owner=u)
            c.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup':setup,
            'teardown':self.teardown,
            'method':'delete',
            'url':'/api/cell/%(cell_id)s/',
            'users': self.users,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 204,
                              }
            }
        return dic

class DropletTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com")
            }

    @test_multiple_users
    def test_read_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="foo", revisions=[CellRevision(name="foo", resource=ur)], owner=u)
            c.save()
            d = Droplet(name="drop", owner=u, cell=c)
            d.save()

            return { 'droplet_id': d.pk }

        dic = {
            'setup':setup,
            'teardown':self.teardown,
            'method':'get',
            'url':'/api/droplet/%(droplet_id)s/',
            'users': self.users,
            'content': '%(droplet_id)s',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }
        return dic

    @test_multiple_users
    def test_create_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="bar", revisions=[CellRevision(name="bar", resource=ur)], owner=u)
            c.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'post',
            'url': '/api/droplet/',
            'users': self.users,
            'content': '%(cell_id)s',
            'postdata': {'name':'drop',
                         'cell':'%(cell_id)s'
                         },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }

        return dic

    @test_multiple_users
    def test_update_name_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="bar", revisions=[CellRevision(name="bar", resource=ur)], owner=u)
            c.save()
            d = Droplet(name='drop', owner=u, cell=c, revisions=[DropletRevision(name="drop", resource=ur)])
            d.save()
            return { 'droplet_id':d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'url': '/api/droplet/%(droplet_id)s/',
            'users': self.users,
            'content': 'newname',
            'postdata': {'name':'newname',
                         'number':'1',
                         },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }

        return dic

    @test_multiple_users
    def test_delete_droplet(self):
        """ delete droplet """
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="bar", revisions=[CellRevision(name="bar", resource=ur)], owner=u)
            c.save()
            d = Droplet(name='drop', owner=u, cell=c, revisions=[DropletRevision(name="d1", resource=ur)])
            d.save()
            return { 'droplet_id':d.pk }

        def extra_checks(response):
            self.assertEqual(Droplet.objects(deleted=True).count(), 1)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'delete',
            'url': '/api/droplet/%(droplet_id)s/',
            'users': self.users,
            'postdata': {'name':'newname',
                         },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 204,
                              },
            'checks':{'owner': extra_checks},
            }

        return dic


    @test_multiple_users
    def test_move_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="bar", revisions=[CellRevision(name="bar", resource=ur)], owner=u)
            c.save()

            c1 = Cell(name="foo", revisions=[CellRevision(name="foo", resource=ur)], owner=u)
            c1.save()
            d = Droplet(name='drop', owner=u, cell=c, revisions=[DropletRevision(name="d1", resource=ur)])
            d.save()
            return { 'droplet_id':d.pk, 'cell_id':c1.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'url': '/api/droplet/%(droplet_id)s/',
            'users': self.users,
            'content': '%(cell_id)s',
            'postdata': {'cell':'%(cell_id)s',
                         'number': 1,
                         },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }

        return dic

    @test_multiple_users
    def test_denied_move_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="melisi")
            ur = UserResource.objects.get(user=u)
            ur1 = UserResource.objects.get(user=u1)

            c = Cell(name="bar", revisions=[CellRevision(name="bar", resource=ur)], owner=u)
            c.save()
            c1 = Cell(name="foo", revisions=[CellRevision(name="foo", resource=ur1)], owner=u1)
            c1.save()
            d = Droplet(name='drop', owner=u, cell=c, revisions=[DropletRevision(name="d1", resource=ur)])
            d.save()
            return { 'droplet_id':d.pk, 'cell_id':c1.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'url': '/api/droplet/%(droplet_id)s/',
            'users': self.users,
            'content': '%(cell_id)s',
            'postdata': {'cell':'%(cell_id)s',
                         },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 401,
                              }
            }

        return dic

class DropletRevisionTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com")
            }

    @test_multiple_users
    def test_read_latest_revision(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewing file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            ur = UserResource.objects.get(user=u)
            c1 = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1, revisions=[DropletRevision(name="d1", resource=ur)])
            d.save()

            # create revision
            r = DropletRevision(resource=ur, name="d1")
            r.content.put(content)
            d.revisions.append(r)
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'url': '/api/droplet/%(droplet_id)s/revision/latest/',
            'users': self.users,
            'content': 'created',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }

        return dic

    @test_multiple_users
    def test_read_specific_revision(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewing file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            ur = UserResource.objects.get(user=u)
            c1 = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1, revisions=[DropletRevision(name="d1", resource=ur)])
            d.save()

            # create revision
            r = DropletRevision(resource=ur, name="d1")
            r.content.new_file()
            r.content.write(content.read())
            r.content.close()
            d.revisions.append(r)
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'url': '/api/droplet/%(droplet_id)s/revision/1/',
            'users': self.users,
            'content': 'created',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }

        return dic

    @test_multiple_users
    def test_create_revision(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            #rewind file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            ur = UserResource.objects.get(user=u)
            c1 = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1, revisions=[DropletRevision(name="d1", resource=ur)])
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'post',
            'url': '/api/droplet/%(droplet_id)s/revision/',
            'users': self.users,
            'content': 'created',
            'postdata': { 'number': '1',
                          'md5': md5,
                          'content': content,
                          },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              }
            }

        return dic

    @test_multiple_users
    def test_denied_create_revision(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = 'foobar-fake-md5'
        content.seek(0)

        def setup():
            #rewind file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            ur = UserResource.objects.get(user=u)
            c1 = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1, revisions=[DropletRevision(name="d1", resource=ur)])
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'post',
            'url': '/api/droplet/%(droplet_id)s/revision/',
            'users': self.users,
            'postdata': { 'number': '1',
                          'md5': md5,
                          'content': content,
                          },
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 400,
                              }
            }

        return dic


    @test_multiple_users
    def test_delete_revision(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewind file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            ur = UserResource.objects.get(user=u)
            c1 = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1, revisions=[DropletRevision(name="d1", resource=ur)])
            d.save()

            # create revision
            r = DropletRevision(name="d1", resource=ur)
            r.content.put(content)
            d.revisions.append(r)
            d.save()

            return { 'droplet_id' : d.pk }

        def extra_checks(response):
            d = Droplet.objects.get(name="d1")
            self.assertEqual(len(d.revisions), 1)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'delete',
            'url': '/api/droplet/%(droplet_id)s/revision/2/',
            'users': self.users,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 204,
                              },
            'checks': {'owner': extra_checks }
            }

        return dic

    @test_multiple_users
    def test_read_latest_revision_content(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewind file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            ur = UserResource.objects.get(user=u)
            c1 = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1, revisions=[DropletRevision(name="d1", resource=ur)])
            d.save()

            # create revision
            r = DropletRevision(resource=ur, content=content, name="d1")
            d.content = r.content
            d.revisions.append(r)
            d.save()
            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'url': '/api/droplet/%(droplet_id)s/revision/latest/content/',
            'users': self.users,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              },
            }

        return dic


    # @test_multiple_users
    # def test_read_latest_revision_patch(self):
    #     import hashlib
    #     import tempfile

    #     content = tempfile.TemporaryFile()
    #     content.write('1234567890\n')
    #     content.seek(0)
    #     md5 = hashlib.md5(content.read()).hexdigest()
    #     content.seek(0)

    #     def setup():
    #         # rewind file
    #         content.seek(0)

    #         u = User.objects.get(username="foo")
    #         # create cell
    #         ur = UserResource.objects.get(user=u)
    #         c1 = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
    #         c1.save()

    #         # create droplet
    #         d = Droplet(name="d1", owner=u, cell=c1, revisions=[DropletRevision(name="d1", resource=ur)])
    #         d.save()

    #         # create revision
    #         r = DropletRevision(resource=ur, patch=content, name="d1")
    #         d.revisions.append(r)
    #         d.content = r.content
    #         d.revisions.append(r)

    #         d.save()

    #         return { 'droplet_id' : d.pk }

    #     dic = {
    #         'setup': setup,
    #         'teardown': self.teardown,
    #         'method': 'get',
    #         'url': '/api/droplet/%(droplet_id)s/revision/latest/patch/',
    #         'users': self.users,
    #         'response_code': {'user': 401,
    #                           'admin': 401,
    #                           'anonymous': 401,
    #                           'owner': 200,
    #                           },
    #         }

    #     return dic


    @test_multiple_users
    def test_read_specific_revision_content(self):
        import hashlib
        import tempfile

        content = tempfile.TemporaryFile()
        content.write('1234567890\n')
        content.seek(0)
        md5 = hashlib.md5(content.read()).hexdigest()
        content.seek(0)

        def setup():
            # rewind file
            content.seek(0)

            u = User.objects.get(username="foo")
            # create cell
            ur = UserResource.objects.get(user=u)
            c1 = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            c1.save()

            # create droplet
            d = Droplet(name="d1", owner=u, cell=c1, revisions=[DropletRevision(name="d1", resource=ur)])
            d.save()

            # create revision
            r = DropletRevision(resource=ur, content=content, name="d1")
            d.revisions.append(r)
            d.content = r.content
            d.save()

            return { 'droplet_id' : d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'url': '/api/droplet/%(droplet_id)s/revision/2/content/',
            'users': self.users,
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              },
            }

        return dic

    # @test_multiple_users
    # def test_read_specific_revision_patch(self):
    #     import hashlib
    #     import tempfile

    #     content = tempfile.TemporaryFile()
    #     content.write('1234567890\n')
    #     content.seek(0)
    #     md5 = hashlib.md5(content.read()).hexdigest()
    #     content.seek(0)

    #     def setup():
    #         # rewind file
    #         content.seek(0)

    #         u = User.objects.get(username="foo")
    #         # create cell
    #         ur = UserResource.objects.get(user=u)
    #         c1 = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
    #         c1.save()

    #         # create droplet
    #         d = Droplet(name="d1", owner=u, cell=c1, revisions=[DropletRevision(name="d1", resource=ur)])
    #         d.save()

    #         # create revision
    #         r = DropletRevision(resource=ur, patch=content, name="d1")
    #         d.revisions.append(r)
    #         d.revisions.append(r)
    #         d.save()

    #         return { 'droplet_id' : d.pk }

    #     dic = {
    #         'setup': setup,
    #         'teardown': self.teardown,
    #         'method': 'get',
    #         'url': '/api/droplet/%(droplet_id)s/revision/2/patch/',
    #         'users': self.users,
    #         'response_code': {'user': 401,
    #                           'admin': 401,
    #                           'anonymous': 401,
    #                           'owner': 200,
    #                           },
    #         }

    #     return dic


    # @test_multiple_users
    # def test_update_revision_patch(self):
    #     import hashlib
    #     import tempfile

    #     content = tempfile.TemporaryFile()
    #     content.write('123456')
    #     content.seek(0)
    #     delta = tempfile.TemporaryFile()
    #     delta.write('72730236410b303132333435363738390a00'.decode('HEX'))
    #     delta.seek(0)
    #     md5 = hashlib.md5(content.read()).hexdigest()
    #     content.seek(0)

    #     def setup():
    #         # rewind file
    #         content.seek(0)
    #         delta.seek(0)

    #         u = User.objects.get(username="foo")
    #         # create cell
    #         ur = UserResource.objects.get(user=u)
    #         c1 = Cell(revisions=[CellRevision(name="c1", resource=ur)], owner=u)
    #         c1.save()

    #         # create droplet
    #         d = Droplet(name="d1", owner=u, cell=c1, revisions=[DropletRevision(name="d1", resource=ur)])
    #         d.save()

    #         # create revision
    #         r = DropletRevision(resource=ur, content=content, name="d1")
    #         d.revisions.append(r)
    #         d.save()

    #         return { 'droplet_id' : d.pk }

    #     dic = {
    #         'setup': setup,
    #         'teardown': self.teardown,
    #         'method': 'put',
    #         'url': '/api/droplet/%(droplet_id)s/revision/',
    #         'users': self.users,
    #         'response_code': {'user': 401,
    #                           'admin': 401,
    #                           'anonymous': 401,
    #                           'owner': 200,
    #                           },
    #         'postdata': { 'number': '1',
    #                       'md5': '3749f52bb326ae96782b42dc0a97b4c1', # md5 of '0123456789'
    #                       'content': delta,
    #                       'patch':'True',
    #                       },
    #         'content': 'created'
    #         }

    #     return dic

    # @test_multiple_users
    # def test_update_revision_nopatch(self):
    #     import hashlib
    #     import tempfile

    #     content = tempfile.TemporaryFile()
    #     content.write('123456')
    #     content.seek(0)
    #     delta = tempfile.TemporaryFile()
    #     delta.write('0123456789\n')
    #     delta.seek(0)
    #     md5 = hashlib.md5(content.read()).hexdigest()
    #     content.seek(0)

    #     def setup():
    #         # rewind file
    #         content.seek(0)
    #         delta.seek(0)

    #         u = User.objects.get(username="foo")
    #         # create cell
    #         ur = UserResource.objects.get(user=u)
    #         c1 = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
    #         c1.save()

    #         # create droplet
    #         d = Droplet(name="d1", owner=u, cell=c1, revisions=[DropletRevision(name="d1", resource=ur)])
    #         d.save()

    #         # create revision
    #         r = DropletRevision(resource=ur, content=content, name="d1")
    #         d.revisions.append(r)
    #         d.save()

    #         return { 'droplet_id' : d.pk }

    #     dic = {
    #         'setup': setup,
    #         'teardown': self.teardown,
    #         'method': 'put',
    #         'url': '/api/droplet/%(droplet_id)s/revision/',
    #         'users': self.users,
    #         'response_code': {'user': 401,
    #                           'admin': 401,
    #                           'anonymous': 401,
    #                           'owner': 200,
    #                           },
    #         'postdata': { 'number': '1',
    #                       'md5': '3749f52bb326ae96782b42dc0a97b4c1', # md5 of '0123456789'
    #                       'content': delta,
    #                       'patch':'False',
    #                       },
    #         'content': 'created'
    #         }

    #     return dic


    # @test_multiple_users
    # def test_denied_update_revision(self):
    #     import hashlib
    #     import tempfile

    #     content = tempfile.TemporaryFile()
    #     content.write('123456')
    #     content.seek(0)
    #     delta = tempfile.TemporaryFile()
    #     delta.write('72730236410b303132333435363738390a00'.decode('HEX'))
    #     delta.seek(0)
    #     md5 = hashlib.md5(content.read()).hexdigest()
    #     content.seek(0)

    #     def setup():
    #         # rewind file
    #         content.seek(0)
    #         delta.seek(0)

    #         u = User.objects.get(username="foo")
    #         # create cell
    #         ur = UserResource.objects.get(user=u)
    #         c1 = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
    #         c1.save()

    #         # create droplet
    #         d = Droplet(name="d1", owner=u, cell=c1, revisions=[DropletRevision(name="d1", resource=ur)])
    #         d.save()

    #         # create revision
    #         r = DropletRevision(resource=ur, content=content, name="d1")
    #         d.revisions.append(r)
    #         d.save()

    #         return { 'droplet_id' : d.pk }

    #     dic = {
    #         'setup': setup,
    #         'teardown': self.teardown,
    #         'method': 'put',
    #         'url': '/api/droplet/%(droplet_id)s/revision/',
    #         'users': self.users,
    #         'response_code': {'user': 401,
    #                           'admin': 401,
    #                           'anonymous': 401,
    #                           'owner': 400,
    #                           },
    #         'postdata': { 'number': '2',
    #                       'md5': 'foo-bar-wrong-md5',
    #                       'patch': delta,
    #                       },
    #         'content': 'created'
    #         }

    #     return dic



class ShareTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'user' : self.create_user(),
            'admin' : self.create_superuser(),
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com"),
            'partner': self.create_user("bar", "bar@example.com"),
            }

    @test_multiple_users
    def test_share_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            c.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup':setup,
            'teardown': self.teardown,
            'postdata': { 'user': 'bar',
                          'mode': 'wara',
                          },
            'response_code': { 'user': 401,
                               'admin': 401,
                               'anonymous': 401,
                               'owner': 201,
                               'partner': 401,
                               },
            'users': self.users,
            'method': 'post',
            'url': '/api/cell/%(cell_id)s/share/'
            }

        return dic

    @test_multiple_users
    def test_denied_share_cell(self):
        """ deny double share root """
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)

            s = Share(user=u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            c1 = Cell(name="c2", revisions=[CellRevision(name="c2", resource=ur)], owner=u, roots=[c])
            c1.save()

            return { 'cell_id': c1.pk }

        dic = {
            'setup':setup,
            'teardown': self.teardown,
            'postdata': { 'user': 'bar',
                          'mode': 'wara',
                          },
            'response_code': { 'user': 401,
                               'admin': 401,
                               'anonymous': 401,
                               'owner': 400,
                               'partner': 401,
                               },
            'users': self.users,
            'method': 'post',
            'url': '/api/cell/%(cell_id)s/share/'
            }

        return dic


    @test_multiple_users
    def test_read_shares(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)

            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            return { 'cell_id': c.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'users': self.users,
            'url': '/api/cell/%(cell_id)s/share/',
            'response_code': { 'user': 401,
                               'admin': 401,
                               'anonymous': 401,
                               'owner': 200,
                               'partner': 401,
                               },
            'content': 'bar',
            }

        return dic

    @test_multiple_users
    def test_read_shared_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)

            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            c1 = Cell(name="c2", revisions=[CellRevision(name="c2", resource=ur)], owner=u, roots=[c])
            c1.save()

            return { 'cell_id': c1.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'users': self.users,
            'url': '/api/cell/%(cell_id)s/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              'partner': 200,
                              },
            'content': '%(cell_id)s'
            }

        return dic

    @test_multiple_users
    def test_read_shared_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            c1 = Cell(name="c2", revisions=[CellRevision(name="c2", resource=ur)], owner=u, roots=[c])
            c1.save()

            d = Droplet(owner=u, cell=c1, name="lala")
            d.save()

            return { 'droplet_id': d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'users': self.users,
            'url': '/api/droplet/%(droplet_id)s/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              'partner': 200,
                              },
            'content': '%(droplet_id)s'
            }

        return dic

    @test_multiple_users
    def test_write_shared_cell(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)

            s = Share(user = u1, mode='wara', name=c.name )
            c.shared_with.append(s)
            c.save()
            return { 'cell_id': c.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'users': self.users,
            'postdata': { 'name':'newname',
                          'number':'1',
                          },
            'url': '/api/cell/%(cell_id)s/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              'partner': 200,
                              },
            'content': 'newname'
            }

        return dic


    @test_multiple_users
    def test_write_shared_cell_move_owner(self):
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            mc = Cell(name="melissi u", revisions=[CellRevision(name="melissi u", resource=ur)], owner=u)
            mc.save()
            mc_2 = Cell(name="subfolder u", revisions=[CellRevision(name="subfolder u", resource=ur)], owner=u)
            mc_2.save()

            u1 = User.objects.get(username="bar")
            ur1 = UserResource.objects.get(user=u1)
            mc1 = Cell(name="melissi u1", revisions=[CellRevision(name="melissi u1", resource=ur1)], owner=u1)
            mc1.save()

            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            s = Share(user = u1, mode='wara', name=c.name, roots=[mc1] )
            c.shared_with.append(s)
            c.save()
            return { 'cell_id': c.pk, 'mc_2':mc_2.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'users': self.users,
            'postdata': { 'parent': '%(mc_2)s',
                          'name':'newname',
                          'number': 1
                          },
            'url': '/api/cell/%(cell_id)s/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              'partner': 401,
                              },
            'content': '%(mc_2)s'
            }

        return dic

    @test_multiple_users
    def test_write_shared_cell_move_partner(self):
        def setup():
            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            mc = Cell(name="melissi u", revisions=[CellRevision(name="melissi u", resource=ur)], owner=u)
            mc.save()

            u1 = User.objects.get(username="bar")
            ur1 = UserResource.objects.get(user=u1)
            mc1 = Cell(name="melissi u1", revisions=[CellRevision(name="melissi u1", resource=ur1)], owner=u1)
            mc1.save()
            mc1_2 = Cell(name="subfolder u1", revisions=[CellRevision(name="subfolder u1", resource=ur1)], owner=u1)
            mc1_2.save()

            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            s = Share(user = u1, mode='wara', name=c.name, roots=[mc1] )
            c.shared_with.append(s)
            c.save()
            return { 'cell_id': c.pk, 'mc1_2':mc1_2.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'users': self.users,
            'postdata': { 'parent': '%(mc1_2)s',
                          'name':'newname',
                          'number':'1',
                          },
            'url': '/api/cell/%(cell_id)s/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 401,
                              'partner': 200,
                              },
            'content': '%(mc1_2)s'
            }

        return dic

    @test_multiple_users
    def test_write_shared_droplet(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)

            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            d = Droplet(owner=u, cell=c, name="lala",
                        revisions=[DropletRevision(name="c1", resource=ur)])
            d.save()

            return { 'droplet_id': d.pk }

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'put',
            'users': self.users,
            'postdata': { 'name':'newname',
                          'number': '1'
                          },
            'url': '/api/droplet/%(droplet_id)s/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 200,
                              'partner': 200,
                              },
            'content': 'newname'
            }

        return dic


    @test_multiple_users
    def test_delete_share_cell(self):
        """ delete all """
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)

            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            return { 'cell_id': c.pk }

        def extra_checks(response):
            # c = Cell.objects.get(name="c1")
            # self.assertEqual(len(c.shared_with), 0)
            pass

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'delete',
            'users': self.users,
            'url': '/api/cell/%(cell_id)s/share/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 204,
                              'partner': 401,
                              },
            'checks': { 'owner' : extra_checks },
            }

        return dic

    @test_multiple_users
    def test_delete_share_user(self):
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)

            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            return { 'cell_id': c.pk, 'username': u1.username }

        def extra_checks(response):
            c = Cell.objects.get(name="c1")
            self.assertEqual(len(c.shared_with), 0)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'delete',
            'users': self.users,
            'url': '/api/cell/%(cell_id)s/share/%(username)s/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 204,
                              'partner': 204,
                              },
            'checks': { 'owner' : extra_checks },
            }

        return dic


    @test_multiple_users
    def test_delete_share_user2(self):
        """ User who is in shared_with list and his not owner
        tries to delete another user in shared_with list
        """
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            u2 = MelissiUser.create_user("sharetest", "test@example.com", "123")

            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)

            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            s1 = Share(user = u2, mode='wara')
            c.shared_with.append(s1)
            c.save()

            return { 'cell_id': c.pk }

        def teardown():
            User.objects(username="sharetest").delete()
            self.teardown()

        def extra_checks(response):
            c = Cell.objects.get(name="c1")
            self.assertEqual(len(c.shared_with), 1)

        dic = {
            'setup': setup,
            'teardown': teardown,
            'method': 'delete',
            'users': self.users,
            'url': '/api/cell/%(cell_id)s/share/sharetest/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 204,
                              'partner': 401,
                              },
            'checks': { 'owner' : extra_checks },
            }

        return dic

    @test_multiple_users
    def test_update_share_cell(self):
        """ update mode for user """
        def setup():
            u = User.objects.get(username="foo")
            u1 = User.objects.get(username="bar")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)

            s = Share(user = u1, mode='wara')
            c.shared_with.append(s)
            c.save()

            return { 'cell_id': c.pk }

        def extra_checks(response):
            c = Cell.objects.get(name="c1")
            self.assertEqual(len(c.shared_with), 1)
            self.assertEqual(c.shared_with[0].mode, 'wnra')

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'post',
            'users': self.users,
            'postdata': { 'user':'bar',
                          'mode':'wnra'
                          },
            'url': '/api/cell/%(cell_id)s/share/',
            'response_code': {'user': 401,
                              'admin': 401,
                              'anonymous': 401,
                              'owner': 201,
                              'partner': 401,
                              },
            'checks': { 'owner' : extra_checks },
            }

        return dic

    @test_multiple_users
    def test_recursive_share_cell(self):
        def setup():
            user_tza = self.create_user(username='tza', email='tza@example.com')
            user_foo = User.objects.get(username='foo')
            user_bar = User.objects.get(username='bar')

            user_bar_root = Cell.objects.get(owner=user_bar)
            user_foo_root = Cell.objects.get(owner=user_foo)

            ur_foo = UserResource.objects.get(user=user_foo)
            ur_bar = UserResource.objects.get(user=user_bar)

            c0 = Cell(name="0", revisions=[CellRevision(name="0", resource=ur_foo)], owner=user_foo, roots=[user_foo_root])

            c0.save()
            c1 = Cell(name="1", revisions=[CellRevision(name="1", resource=ur_bar)], owner=user_bar, roots=[user_bar_root])
            c1.shared_with.append(Share(name='1',
                                        user=user_foo,
                                        mode='wara',
                                        roots = [c0, user_foo_root]
                                        )
                                  )
            c1.save()
            return { 'cell_id': c0.pk }

        def extra_checks(response):
            c1 = Cell.objects.get(name='1')
            self.assertEqual(len(c1.shared_with), 2)

            c0 = Cell.objects.get(name='0')
            self.assertEqual(len(c0.shared_with), 1)

        def teardown():
            # delete user tza
            User.objects.get(username='tza').delete()
            self.teardown()

        dic = {
            'setup':setup,
            'teardown': teardown,
            'postdata': {'user': 'tza',
                         'mode': 'wara',
                         },
            'response_code': { 'user': 401,
                               'admin': 401,
                               'anonymous': 401,
                               'owner': 201,
                               'partner': 401,
                               },
            'users': self.users,
            'method': 'post',
            'url': '/api/cell/%(cell_id)s/share/',
            'checks': {'owner': extra_checks }
            }

        return dic


class StatusTest(AuthTestCase):
    def setUp(self):
        self.users = {
            'anonymous': self.create_anonymous(),
            'owner': self.create_user("foo", "foo@example.com"),
            }

    @test_multiple_users
    def test_share_cell_all(self):
        """ get all updates """
        def setup():
            from datetime import datetime, timedelta
            # timestamp
            now = datetime.now()
            a_month_ago = datetime.now() - timedelta(days=30)
            a_day_ago = datetime.now() - timedelta(days=1)

            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            c.save()
            # force updated timestamp
            Cell.objects(pk=c.pk).update(set__updated=now)

            c1 = Cell(name="c2", revisions=[CellRevision(name="c2", resource=ur)], owner=u, roots=[c])
            c1.save()
            # force updated timestamp
            Cell.objects(pk=c1.pk).update(set__updated=a_month_ago)

            c2 = Cell(name="c3", revisions=[CellRevision(name="c3", resource=ur)], owner=u, roots=[c])
            c2.save()
            # force updated timestamp
            Cell.objects(pk=c2.pk).update(set__updated=a_day_ago)


            d = Droplet(name="d1", owner=u, cell=c)
            # create revision
            r = DropletRevision(resource=ur)
            r.content.put("")
            d.revisions.append(r)
            d.save()
            # force updated timestamp
            Droplet.objects(pk=d.pk).update(set__updated=now)


            d1 = Droplet(name="d2", owner=u, cell=c)
            # create revision
            r = DropletRevision(resource=ur)
            r.content.put("")
            d1.revisions.append(r)
            d1.save()
            # force updated timestamp
            Droplet.objects(pk=d1.pk).update(set__updated=a_month_ago)

            d2 = Droplet(name="d3", owner=u, cell=c)
            # create revision
            r = DropletRevision(resource=ur)
            r.content.put("")
            d2.revisions.append(r)
            d2.save()
            # force updated timestamp
            Droplet.objects(pk=d2.pk).update(set__updated=a_day_ago)

        def extra_checks(response):
            result = json.loads(response.content)
            self.assertEqual(len(result['reply']['cells']), 4)
            self.assertEqual(len(result['reply']['droplets']), 3)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'users': self.users,
            'url': '/api/status/all/',
            'response_code': {'anonymous': 401,
                              'owner': 200
                              },
            'checks': {'owner': extra_checks },
            }

        return dic


    @test_multiple_users
    def test_share_cell(self):
        """ no arguments, get last 24 hours """
        def setup():
            from datetime import datetime, timedelta
            # timestamp
            now = datetime.now()
            a_month_ago = datetime.now() - timedelta(days=30)
            a_day_ago = datetime.now() - timedelta(hours=23)

            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            c.save()
            # force updated timestamp
            Cell.objects(pk=c.pk).update(set__updated=a_month_ago)

            c1 = Cell(name="c2", revisions=[CellRevision(name="c2", resource=ur)], owner=u, roots=[c])
            c1.save()
            # force updated timestamp
            Cell.objects(pk=c1.pk).update(set__updated=a_month_ago)

            c2 = Cell(name="c3", revisions=[CellRevision(name="c3", resource=ur)], owner=u, roots=[c])
            c2.save()
            # force updated timestamp
            Cell.objects(pk=c2.pk).update(set__updated=a_day_ago)


            d = Droplet(name="d1", owner=u, cell=c)
            # create revision
            r = DropletRevision(resource=ur)
            r.content.put("")
            d.revisions.append(r)
            d.save()
            # force updated timestamp
            Droplet.objects(pk=d.pk).update(set__updated=now)

            d1 = Droplet(name="d2", owner=u, cell=c)
            # create revision
            r = DropletRevision(resource=ur)
            r.content.put("")
            d1.revisions.append(r)
            d1.save()
            # force updated timestamp
            Droplet.objects(pk=d1.pk).update(set__updated=a_month_ago)

            d2 = Droplet(name="d3", owner=u, cell=c)
            # create revision
            r = DropletRevision(resource=ur)
            r.content.put("")
            d2.revisions.append(r)
            d2.save()
            # force updated timestamp
            Droplet.objects(pk=d2.pk).update(set__updated=a_day_ago)

        def extra_checks(response):
            result = json.loads(response.content)
            self.assertEqual(len(result['reply']['cells']), 2)
            self.assertEqual(len(result['reply']['droplets']), 2)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'users': self.users,
            'url': '/api/status/',
            'response_code': {'anonymous': 401,
                              'owner': 200
                              },
            'checks': {'owner': extra_checks },
            }

        return dic

    @test_multiple_users
    def test_share_cell_after(self):
        """ after a specific date """
        def setup():
            from datetime import datetime, timedelta
            import time
            # timestamp
            now = datetime.now()
            a_month_ago = datetime.now() - timedelta(days=30)
            a_day_ago = datetime.now() - timedelta(hours=23)

            u = User.objects.get(username="foo")
            ur = UserResource.objects.get(user=u)
            c = Cell(name="c1", revisions=[CellRevision(name="c1", resource=ur)], owner=u)
            c.save()
            # force updated timestamp
            Cell.objects(pk=c.pk).update(set__updated=a_month_ago)

            c1 = Cell(name="c2", revisions=[CellRevision(name="c2", resource=ur)], owner=u, roots=[c])
            c1.save()
            # force updated timestamp
            Cell.objects(pk=c1.pk).update(set__updated=a_month_ago)

            c2 = Cell(name="c3", revisions=[CellRevision(name="c3", resource=ur)], owner=u, roots=[c])
            c2.save()
            # force updated timestamp
            Cell.objects(pk=c2.pk).update(set__updated=a_day_ago)


            d = Droplet(name="d1", owner=u, cell=c)
            # create revision
            r = DropletRevision(resource=ur)
            r.content.put("")
            d.revisions.append(r)
            d.save()
            # force updated timestamp
            Droplet.objects(pk=d.pk).update(set__updated=now)

            d1 = Droplet(name="d2", owner=u, cell=c)
            # create revision
            r = DropletRevision(resource=ur)
            r.content.put("")
            d1.revisions.append(r)
            d1.save()
            # force updated timestamp
            Droplet.objects(pk=d1.pk).update(set__updated=a_month_ago)

            d2 = Droplet(name="d3", owner=u, cell=c)
            # create revision
            r = DropletRevision(resource=ur)
            r.content.put("")
            d2.revisions.append(r)
            d2.save()
            # force updated timestamp
            Droplet.objects(pk=d2.pk).update(set__updated=a_day_ago)

            return {'timestamp': time.time() - 3600*2 }

        def extra_checks(response):
            result = json.loads(response.content)
            self.assertEqual(len(result['reply']['cells']), 1)
            self.assertEqual(len(result['reply']['droplets']), 1)

        dic = {
            'setup': setup,
            'teardown': self.teardown,
            'method': 'get',
            'users': self.users,
            'url': '/api/status/after/%(timestamp)s/',
            'response_code': {'anonymous': 401,
                              'owner': 200
                              },
            'checks': {'owner': extra_checks },
            }

        return dic
