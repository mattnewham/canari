#!/usr/bin/env python

import os
import subprocess
import sys
import unicodedata
from canari.utils.fs import fmutex

from pkg_resources import resource_filename
from distutils.dist import Distribution
from distutils.command.install import install
from datetime import datetime
from string import Template

from canari.config import CanariConfigParser
import threading



def synchronized(func):

    func.__lock__ = threading.RLock()

    def synced_func(*args, **kws):
        with func.__lock__:
            return func(*args, **kws)

    return synced_func

__author__ = 'Nadeem Douba'
__copyright__ = 'Copyright 2012, Canari Project'
__credits__ = []

__license__ = 'GPL'
__version__ = '0.2'
__maintainer__ = 'Nadeem Douba'
__email__ = 'ndouba@gmail.com'
__status__ = 'Development'

def fix_etree():
    try:
        from xml.etree.cElementTree import XML
        e = XML('<test><t a="1"/></test>')
        e.find('t[@a="1"]')
    except SyntaxError:
        import canari.xmltools.fixetree

def get_bin_dir():
    d = install(Distribution())
    d.finalize_options()
    return d.install_scripts


def get_commands(module='canari.commands'):
    commands = {}
    sc = __import__(module, globals(), locals(), fromlist=['__all__'])
    for c in sc.__all__:
        m = __import__('%s.%s' % (module, c), globals(), locals(), fromlist=['run', 'help'])
        if 'run' in m.__dict__:
            commands[cmd_name(m.__name__)] = m
    return commands


def _detect_settings_dir(d):
    vs = [ i for i in os.listdir(d) if os.path.isdir(os.path.join(d, i)) if os.path.isdir(os.path.join(d, i, 'config'))]
    if len(vs) == 1:
        return os.path.join(d, vs[0])
    else:
        while True:
            print('Multiple versions of Maltego detected: ')
            for i, v in enumerate(vs):
                print('[%d] Maltego %s' % (i, v))
            r = raw_input('Please select which version you wish to use [0]: ')
            try:
                if not r:
                    return os.path.join(d, vs[0])
                elif int(r) < len(vs):
                    return os.path.join(d, vs[int(r)])
            except ValueError:
                pass
            print('Invalid selection... %s' % repr(r))
    print('Could not automatically find Maltego\'s settings directory. Use the -w parameter to specify its location, instead.')


def to_utf8(s):
    return unicodedata.normalize('NFKD', unicode(s)).encode('ascii', 'ignore')


def detect_settings_dir():
    d = None
    if sys.platform.startswith('linux'):
        d = _detect_settings_dir(os.path.join(os.path.expanduser('~'), '.maltego'))
    elif sys.platform == 'darwin':
        d = _detect_settings_dir(os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'maltego'))
    elif sys.platform == 'win32':
        d = _detect_settings_dir(os.path.join(os.environ['APPDATA'], '.maltego'))
    else:
        raise NotImplementedError('Unknown or unsupported OS: %s' % repr(sys.platform))
    return d


def sudo(args):
    p = subprocess.Popen([os.path.join(get_bin_dir(), 'pysudo')] + args, stdin=subprocess.PIPE)
    p.communicate()
    return p.returncode


def read_template(name, values):
    t = Template(file(resource_filename('canari.resources.template', '%s.plate' % name)).read())
    return t.substitute(**values)


def write_template(fname, data):
    print('creating file %s...' % fname)
    with file(fname, mode='wb') as w:
        w.write(data)


def generate_all(*args):
    return "\n\n__all__ = [\n    '%s'\n]" % "',\n    '".join(args)


def build_skeleton(*args):
    for d in args:
        if isinstance(d, list):
            d = os.sep.join(d)
        print('creating directory %s' % d)
        os.mkdir(d)


def highlight(s, color, bold):

    if os.name == 'posix':
        attr = []
        if color == 'green':
            # green
            attr.append('32')
        elif color == 'red':
            # red
            attr.append('31')
        else:
            attr.append('30')
        if bold:
            attr.append('1')
        s = '\x1b[%sm%s\x1b[0m' % (';'.join(attr), s)

    return s


def croak(exc):
    print(highlight(exc, 'red', None))


def fix_pypath():
    if '' not in sys.path:
        sys.path.insert(0, '')


def fix_binpath(paths):
    if paths is not None:
        if isinstance(paths, basestring):
            os.environ['PATH'] = paths
        elif isinstance(paths, list):
            os.environ['PATH'] = os.pathsep.join(paths)


def import_transform(script):
    fix_pypath()
    return __import__(script, globals(), locals(), ['dotransform'])


def import_package(package):
    fix_pypath()
    return __import__(package, globals(), locals(), ['*'])


def cmd_name(name):
    return name.replace('canari.commands.', '').replace('_', '-')


def console_message(msg, tab=-1):
    tab += 1
    print('%s`- %s: %s %s' % (
        '  ' * tab,
        highlight(msg.tag, None, True),
        highlight(msg.text, 'red', False) if msg.text is not None else '',
        highlight(msg.attrib, 'green', True) if msg.attrib.keys() else ''
        ))
    for c in msg.getchildren():
        print('  %s`- %s: %s %s' % (
            '  ' * tab,
            highlight(c.tag, None, True),
            highlight(c.text, 'red', False) if c.text is not None else '',
            highlight(c.attrib, 'green', True) if c.attrib.keys() else ''
            ))
        for sc in c.getchildren():
            tab += 1
            console_message(sc, tab)
            tab -= 1
    tab -= 1


def init_pkg():

    root = project_root()

    if root is not None:
        conf = os.path.join(root, '.canari')
        if os.path.exists(conf):
            c = CanariConfigParser()
            c.read(conf)
            return {
                'author' : c['metadata/author'],
                'email' : c['metadata/email'],
                'maintainer' : c['metadata/maintainer'],
                'project' : c['metadata/project'],
                'year' : datetime.now().year
            }

    return {
        'author' : '',
        'email' : '',
        'maintainer' : '',
        'project' : '',
        'year' : datetime.now().year
    }


def project_root():

    marker = '.canari'

    for i in range(0, 5):
        if os.path.exists(marker):
            return os.path.dirname(os.path.realpath(marker))
        marker = '..%s%s' % (os.sep, marker)

    print 'Unable to determine project root.'
    exit(-1)


def project_tree():

    root = project_root()

    tree = dict(
        root=root,
        src=None,
        pkg=None,
        resources=None,
        transforms=None
    )

    for base, dirs, files in os.walk(root):
        if base.endswith('src'):
            tree['src'] = base
        elif 'resources' in dirs:
            tree['pkg'] = base
        elif base.endswith('resources'):
            tree['resources'] = base
        elif base.endswith('transforms'):
            tree['transforms'] = base

    return tree


def parse_bool(ans, default='y'):

    while True:
        ans = raw_input(ans).lower() or default
        if ans.startswith('y'):
            return True
        elif ans.startswith('n'):
            return False