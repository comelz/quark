from quark import checkout, freeze, status, update, mirror

commands = [
    ('checkout', checkout.run),
    ('freeze', freeze.run),
    ('status', status.run),
    ('update', update.run),
    ('mirror', mirror.run),
]

aliases = [('co', 'checkout'),
           ('up', 'update'),
           ('fz', 'freeze'),
           ('st', 'status')]

def mk_setup_entry_points():
    res = ["quark=quark.cli:main"]
    for cmd, fn in commands:
        res.append("quark-%s=%s:%s" % (cmd, fn.__module__, fn.__qualname__))
    dcommands = dict(commands)
    for alias, cmd in aliases:
        fn = dcommands[cmd]
        res.append("quark-%s=%s:%s" % (alias, fn.__module__, fn.__qualname__))
    return res
