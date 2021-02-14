from abc import abstractmethod, ABC
import argparse
import collections
import configparser
import hashlib
import os
import re
import zlib
import sys


class GitRepository:
    """A git repository"""

    worktree = None # where all the files are
    gitdir = None # .git directory
    conf = None
    
    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")
        
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuartion file missing")

        if not force:
           vers = int(self.conf.get("core", "repositoryformatversion"))
           if vers != 0:
               raise Exception(f"Unsupported repositoryformatversion {vers}")


def repo_path(repo, *path):
    """Compute path under repo's gitdir"""
    return os.path.join(repo.gitdir, *path)


def repo_file(repo, *path, mkdir=False):
    """ Same as repo_path, but create dirname(*path) if absent.  For example, repo_file(r, \"refs\", \"remotes\", \"origin\", \"HEAD\") 
    will create .git/refs/remotes/origin. So it doesnt't create a directory for the last component in *path"""
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)


def repo_dir(repo, *path, mkdir=False):
    """Same as repo_dir, but creates a dir if absent"""
    path = repo_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        else:
            raise Exception(f"Not a directory {path}")
    
    if mkdir:
        os.makedirs(path)
        return path


def repo_create(path):
    """Create new repository at path"""
    
    repo = GitRepository(path, True)

    # Make sure path doesn't exists or is empty dir
    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"{path} is not a direcotry")
        # Not sure if this thing below is needed
        # if os.listdir(repo.worktree):
        #     raise Exception(f"{path} is not empty")
    else:
        os.makedirs(repo.worktree)
    
    # Create all needed directories in .git 
    assert(repo_dir(repo, "branches", mkdir=True))
    assert(repo_dir(repo, "objects", mkdir=True))
    assert(repo_dir(repo, "refs", "tags", mkdir=True))
    assert(repo_dir(repo, "refs", "heads", mkdir=True))

    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")
    
    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)
        
    return repo


def repo_default_config():
    ret = configparser.ConfigParser()
    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")
    return ret


def repo_find(path=".", required=True):
    """Recursively looks for repositories starting from current directory back until root ('/')"""
    path = os.path.realpath(path)
    
    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)
    
    parent = os.path.realpath(os.path.join(path, ".."))
    # means we reached the root directory '/'
    if parent == path:
        if required:
            raise Exception("No git repository")
        else:
            return None
    
    return repo_find(parent, required)


class GitObject(ABC):
    """
    HOW GIT STORES FILES:
    At its core, Git is a “content-addressed filesystem”. That means that unlike regular filesystems, where the name of a file is arbitrary and unrelated to that file’s contents, the names of files as stored by Git are mathematically derived from their contents. This has a very important implication: if a single byte of, say, a text file, changes, its internal name will change, too. To put it simply: you don’t modify a file, you create a new file in a different location. Objects are just that: files in the git repository, whose path is determined by their contents.
    
    HASH FORMAT:
    An object starts with a header that specifies its type: blob, commit, tag or tree. This header is followed by an ASCII space (0x20), then the size of the object in bytes as an ASCII number, then null (0x00) (the null byte), then the contents of the object.
    """
    repo = None
    
    def __init__(self, repo, data=None):
        self.repo = repo 

        if data is not None:
            self.deserialize(data)
    
    @abstractmethod
    def serialize(self):
        raise NotImplementedError("Serialization not implemented")
    
    def deserialize(self, data):
        raise NotImplementedError("Deserialization not implemented")


class GitCommit(GitObject):
    def deserialize(self, data):
        raise NotImplementedError("Serialization not implemented")


class GitTree(GitObject):
    def deserialize(self, data):
        raise NotImplementedError("Serialization not implemented")


class GitTag(GitObject):
    def deserialize(self, data):
        raise NotImplementedError("Serialization not implemented")


class GitBlob(GitObject):
    """
    Of the four Git object types, blobs are the simplest, because they have no actual format. Blobs are user content: every file you put in git is stored as a blob. That make them easy to manipulate, because they have no actual syntax or constraints beyond the basic object storage mechanism: they’re just unspecified data. Creating a GitBlob class is thus trivial, the serialize and deserialize functions just have to store and return their input unmodified.
    """
    fmt = b'blob'
    
    def serialize(self):
        return self.blobdata
    
    def deserialize(self, data):
        self.blobdata = data


def object_read(repo, sha):
    """
    Reads and returns GitObject from .git/objects, based on objects hash (sha).
    Eq. sha=e673d1b7eaa0aa01b5bc2442d570a765bdaae751
    path to the object will be: .git/objects/e6/73d1b7eaa0aa01b5bc2442d570a765bdaae751
    """
    path = repo_file(repo, "objects", sha[:2], sha[2:])
    
    with open(path, 'rb') as f:
        raw = zlib.decompress(f.read())

        # read object type
        x = raw.find(b' ')
        fmt = raw[0:x]
        
        # read and validate object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw) - y - 1:
            raise Exception(f"Malformed object {sha}: bad length")
        
        # pick constructor
        if   fmt==b'commit' : c=GitCommit
        elif fmt==b'tree'   : c=GitTree
        elif fmt==b'tag'    : c=GitTag
        elif fmt==b'blob'   : c=GitBlob
        else:
            raise Exception(f"Unknown type {fmt.decode('ascii')} for object {sha}")
        
        return c(repo, raw[y+1:])


def object_find(repo, name, fmt=None, follow=True):
    """Placeholder"""
    return name


def object_write(obj, actually_write=True):
    data = obj.serialize()
    
    # add header
    res = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    
    # compute hash
    sha = hashlib.sha1(res).hexdigest()
    
    if actually_write:
        path = repo_file(obj.repo, "objects", sha[:2], sha[2:], mkdir=True)

        with open(path, 'wb') as f:
            f.write(zlib.compress(res))
    return sha


def object_hash(fd, fmt, repo=None):
    data = fd.read()
    
    if   fmt==b'commit' : obj=GitCommit(repo, data)
    elif fmt==b'tree'   : obj=GitTree(repo, data)
    elif fmt==b'tag'    : obj=GitTag(repo, data)
    elif fmt==b'blob'   : obj=GitBlob(repo, data)
    else:
        raise Exception(f"Unknown type {fmt}!")

    return object_write(obj, repo)


def cmd_init(args):
    return repo_create(args.path)


def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())


def cmd_cat_file(args):
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())


def cmd_checkout(args):
    pass


def cmd_commit(args):
    pass


def cmd_hash_object(args):
    if args.write:
        repo = repo_find('.')
    else:
        repo = None
    
    with open(args.path, 'rb') as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)


def cmd_log(args):
    pass


def cmd_ls_tree(args):
    pass
    

def cmd_merge(args):
    pass


def cmd_rebase(args):
    pass


def cmd_rev_parse(args):
    pass


def cmd_rm(args):
    pass


def cmd_show_ref(args):
    pass


def cmd_tag(args):
    pass


def cmd_add(args):
    pass


argparser = argparse.ArgumentParser(description="The stupid content tracker")

argsubparser = argparser.add_subparsers(title="Commands", dest='command')
argsubparser.required = True

# sit init PATH
argsp = argsubparser.add_parser("init", help="Initialize new repository")
argsp.add_argument("path",
                   metavar="directory",
                   nargs="?",
                   default=".",
                   help="Where to create the repository.")

# sit cat-file TYPE OBJECT
argsp = argsubparser.add_parser("cat-file",
                                 help="Provide content of repository objects")
argsp.add_argument("type",
                   metavar="type",
                   choices=["blob", "commit", "tag", "tree"],
                   help="Specify the type")
argsp.add_argument("object",
                   metavar="object",
                   help="The object to display")

# git hash-object [-w] [-t TYPE] FILE
argsp = argsubparser.add_parser(
    "hash-object",
    help="Compute object ID and optionally creates a blob from a file")
argsp.add_argument("-t",
                   metavar="type",
                   dest="type",
                   choices=["blob", "commit", "tag", "tree"],
                   default="blob",
                   help="Specify the type")
argsp.add_argument("-w",
                   dest="write",
                   action="store_true",
                   help="Actually write the object into the database")
argsp.add_argument("path",
                   help="Read object from <file>")


commands = {
        "add": cmd_add,
        "cat-file": cmd_cat_file,
        "checkout": cmd_checkout,
        "commit": cmd_commit,
        "hash-object": cmd_hash_object,
        "init": cmd_init,
        "log": cmd_log,
        "ls-tree": cmd_ls_tree,
        "merge": cmd_merge,
        "rebase": cmd_rebase,
        "rev-parse": cmd_rev_parse,
        "rm": cmd_rm,
        "show-ref": cmd_show_ref,
        "tag": cmd_tag
    }


def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)
    commands[args.command](args)
