import re
from abc import abstractmethod, ABC
import os
import collections
import hashlib
import zlib
from repository import repo_dir, repo_file, repo_find

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


def object_resolve(repo, name):
    """
    Resolve name to an object hash in repo.

    This function is aware of:

    - the HEAD literal
    - short and long hashes
    - tags
    - branches
    - remote branches
    """
    candidates = list()
    hashRE = re.compile(r"^[0-9A-Fa-f]{1,16}$")
    smallHashRE = re.compile(r"^[0-9A-Fa-f]{1,16}$")

    # Empty string?  Abort.
    if not name.strip():
        return None

    # Head is nonambiguous
    if name == "HEAD":
        return [ ref_resolve(repo, "HEAD") ]


    if hashRE.match(name):
        if len(name) == 40:
            # This is a complete hash
            return [ name.lower() ]
        elif len(name) >= 4:
            # This is a small hash 4 seems to be the minimal length
            # for git to consider something a short hash.
            # This limit is documented in man git-rev-parse
            name = name.lower()
            prefix = name[0:2]
            path = repo_dir(repo, "objects", prefix, mkdir=False)
            if path:
                rem = name[2:]
                for f in os.listdir(path):
                    if f.startswith(rem):
                        candidates.append(prefix + f)

    return candidates


def object_find(repo, name, fmt=None, follow=True):
    """
    - If name is HEAD, it will just resolve .git/HEAD;
    - If name is a full hash, this hash is returned unmodified.
    - If name looks like a short hash, it will collect objects whose full hash begin with this short hash.
    At last, it will resolve tags and branches matching name.
    """
    sha = object_resolve(repo, name)

    if not sha:
        raise Exception("No such reference {0}.".format(name))

    if len(sha) > 1:
        raise Exception("Ambiguous reference {0}: Candidates are:\n - {1}.".format(name,  "\n - ".join(sha)))

    sha = sha[0]

    if not fmt:
        return sha

    while True:
        obj = object_read(repo, sha)

        if obj.fmt == fmt:
            return sha

        if not follow:
            return None

        # Follow tags
        if obj.fmt == b'tag':
            sha = obj.kvlm[b'object'].decode("ascii")
        elif obj.fmt == b'commit' and fmt == b'tree':
            sha = obj.kvlm[b'tree'].decode("ascii")
        else:
            return None 


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

    
class GitCommit(GitObject):
    """
    ## COMMIT EXAMPLE:

    tree 29ff16c9c14e2652b22f8b78bb08a5a07930c147
    parent 206941306e8a8af65b66eaaaea388a7ae24d49a0
    author Thibault Polge <thibault@thb.lt> 1527025023 +0200
    committer Thibault Polge <thibault@thb.lt> 1527025044 +0200
    gpgsig -----BEGIN PGP SIGNATURE-----

    iQIzBAABCAAdFiEExwXquOM8bWb4Q2zVGxM2FxoLkGQFAlsEjZQACgkQGxM2FxoL
    kGQdcBAAqPP+ln4nGDd2gETXjvOpOxLzIMEw4A9gU6CzWzm+oB8mEIKyaH0UFIPh
    rNUZ1j7/ZGFNeBDtT55LPdPIQw4KKlcf6kC8MPWP3qSu3xHqx12C5zyai2duFZUU
    wqOt9iCFCscFQYqKs3xsHI+ncQb+PGjVZA8+jPw7nrPIkeSXQV2aZb1E68wa2YIL
    3eYgTUKz34cB6tAq9YwHnZpyPx8UJCZGkshpJmgtZ3mCbtQaO17LoihnqPn4UOMr
    V75R/7FjSuPLS8NaZF4wfi52btXMSxO/u7GuoJkzJscP3p4qtwe6Rl9dc1XC8P7k
    NIbGZ5Yg5cEPcfmhgXFOhQZkD0yxcJqBUcoFpnp2vu5XJl2E5I/quIyVxUXi6O6c
    /obspcvace4wy8uO0bdVhc4nJ+Rla4InVSJaUaBeiHTW8kReSFYyMmDCzLjGIu1q
    doU61OM3Zv1ptsLu3gUE6GU27iWYj2RWN3e3HE4Sbd89IFwLXNdSuM0ifDLZk7AQ
    WBhRhipCCgZhkj9g2NEk7jRVslti1NdN5zoQLaJNqSwO1MtxTmJ15Ksk3QP6kfLB
    Q52UWybBzpaP9HEd4XnR+HuQ4k2K0ns2KgNImsNvIyFwbpMUyUWLMPimaV1DWUXo
    5SBjDB/V/W2JBFR+XKHFJeFwYhj7DD/ocsGr4ZMx/lgc8rjIBkI=
    =lgTX
    -----END PGP SIGNATURE-----

    Create first draft


    ## So what makes a commit? To sum it up:

    - A tree object, which we’ll discuss now, that is, the contents of a worktree, files and directories;
    - Zero, one or more parents;
    - An author identity (name and email);
    - A committer identity (name and email);
    - An optional PGP signature
    - A message;
    **All this hashed together in a SHA-1 identifier!!!**

    ## Let’s have a look at those fields:

    - tree is a reference to a tree object, a type of object that we’ll see soon. A tree maps blobs IDs to filesystem locations, and describes a state of the work tree. Put simply, it is the actual content of the commit: files, and where they go.

    - parent is a reference to the parent of this commit. It may be repeated: merge commits, for example, have multiple parents. It may also be absent: the very first commit in a repository obviously doesn’t have a parent.

    - author and committer are separate, because the author of a commit is not necessarily the person who can commit it (This may not be obvious for GitHub users, but a lot of projects do Git through e-mail)

    - gpgsig is the PGP signature of this object.
    """

    fmt = b'commit'
    
    def deserialize(self, data):
        self.msg = message_parse(data)
    
    def serialize(self):
        return message_serialize(self.msg)


def message_parse(raw, start=0, dct=None):
    """Parse commit"""
    if not dct:
        dct = collections.OrderedDict()
    
    # search for location of first space and newline after start location
    spc = raw.find(b' ', start)
    nl = raw.find(b'\n', start)
    
    # base case
    if spc < 0 or nl < spc:
        assert(nl == start)
        dct[b''] = raw[start+1:]
        return dct
    
    key = raw[start:spc]
    end = start
    
    # Find the end of the value.  Continuation lines begin with a
    # space, so we loop until we find a "\n" not followed by a space.
    while True:
        end = raw.find(b'\n', end+1)
        if raw[end+1] != ord(' '): break

    # get the value from raw, drop leading space on continuation line
    value = raw[spc+1:end].replace(b'\n ', b'\n')
    
    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value) 
        else:
            dct[key] = [dct[key], value]
    else:
        dct[key] = value
    
    return message_parse(raw, start=end + 1, dct=dct)


def message_serialize(msg):
    ret = b''

    for k in msg.keys():
        if k == b'':
            continue
        value = msg[k]
        if type(value) != list:
            value = [value]

        for v in value:
            ret += k + b' ' + (v.replace(b'\n', b'\n ')) + b'\n'

    ret += b'\n' + msg[b'']
    return ret

        
def log_graphviz(repo, sha, seen):
    if sha in seen:
        return
    seen.add(sha)

    commit = object_read(repo, sha)
    assert(commit.fmt == b'commit')

    if not b'parent' in commit.msg.keys():
        return
    
    parents = commit.msg[b'parent']
    if type(parents) != list:
        parents = [parents]
    
    for parent in parents:
        parent = parent.decode("ascii")
        print(f"c_{sha} -> c_{parent}")
        log_graphviz(repo, parent, seen)


class GitTree(GitObject):
    """
    Informally, a tree describes the content of the work tree, 
    that it, it associates blobs to paths. 
    It’s an array of three-element tuples made of a file mode, 
    a path (relative to the worktree) and a SHA-1.
    
    Eg.
    Mode    SHA-1                                       Path
    100644  894a44cc066a027465cd26d634948d56d13af9af    README.md
    100644  6d208e47659a2a10f5f8640e0155d9276a2130a9    src
    
    Mode is files permission setting
    
    The SHA-1 refers to either a blob or another tree object. 
    If a blob, the path is a file, if a tree, it’s directory. 
    To instantiate this tree in the filesystem, we would begin by 
    loading the object associated to the first path (README.md) 
    and check its type. Since it’s a blob, we’ll just create a file 
    called README.md with this blob’s contents;
    But the object associated with src is not a blob, 
    but another tree: we’ll create the directory src and repeat 
    the same operation in that directory with the new tree.

    A tree is the concatenation of records of the format:
    [mode] space [path] 0x00 [sha-1]
    
    - [mode] is up to six bytes and is an ASCII representation of a file mode. For example, 100644 is encoded with byte values 49 (ASCII “1”), 48 (ASCII “0”), 48, 54, 52, 52.
    - It’s followed by 0x20, an ASCII space;
    - Followed by the null-terminated (0x00) path;
    - Followed by the object’s SHA-1 in binary encoding, on 20 bytes. Why binary? God only knows.
    """
    
    fmt = b'tree'

    def deserialize(self, data):
        self.entries = tree_parse(data)
    
    def serialize(self):
        return tree_serialize(self)


class GitTreeLeaf:
    def __init__(self, mode, path, sha):
        self.mode = mode
        self.path = path
        self.sha = sha


def tree_parse_leaf(raw, start=0):
    # find space
    spc = raw.find(b' ', start)
    assert(spc - start in [5, 6])

    # read mode
    mode = raw[start:spc]

    # find nulltermination
    nt = raw.find(b'\x00', spc)
    path = raw[spc+1:nt]

    # read sha
    sha = hex(
        int.from_bytes(raw[nt+1:nt+21], "big")
    )[2:] # hex adds "0x" in front, we need to drop that

    return nt + 21, GitTreeLeaf(mode, path, sha)


def tree_parse(raw):
    pos, length = 0, len(raw)
    leaves = []
    while pos < length:
        pos, leaf = tree_parse_leaf(raw, pos)
        leaves.append(leaf)
    return leaves


def tree_serialize(obj):
    ret = b''
    for i in obj.items:
        ret += i.mode
        ret += b' '
        ret += i.path
        ret += b'\x00'
        sha = int(i.sha, 16)
        ret += sha.to_bytes(20, byteorder="big")
    return ret


def tree_checkout(repo, tree, path):
    for entry in tree.entries:
        obj = object_read(repo, entry.sha) 
        dest = os.path.join(path, entry.path)

        if obj.fmt == b'tree':
            os.mkdir(dest)
            tree_checkout(repo, obj, dest)
        elif obj.fmt == b'blob':
            with open(dest, 'wb') as f:
                f.write(obj.blobdata)




class GitTag(GitCommit):
    """
    REFS:
    reft are a type of file stored in .git/refs. They contain hexadeciman hashcodes of objects encoded in ASCII. 

    Eq.: 6071c08bcb4757d8c89a30d9755d2466cef8c1de
    They can also refer to another reference (which makes them indirect refs):
    ref: refs/remotes/origin/master


    TAGS:
    Tags are user defined names for objects, often commits. 
    Tags are actually refs. They live in .git/refs/tags.

    Lightweight tags: 
    are just regular refs to a commit, tree or blob.

    Tag objects:
    are regular refs pointing to an object of type tag. Unlike lightweight tags, tag objects have an author, a date, an optional PGP signature and an optional annotation. Their format is the same as a commit object.


    BRANCHES:
    Commits are grouped in branches, and that at every point in time there’s a commit that’s HEAD, ie, the head commit of the current branch.

    A branch is a reference to a commit. You could even say that a branch is a kind of a name for a commit. In this regard, a branch is exactly the same thing as a tag. Tags are refs that live in .git/refs/tags, branches are refs that live in .git/refs/heads.

    Branches are references to a commit, tags can refer to any object;
    But most importantly, the branch ref is updated at each commit. 
    This means that whenever you commit, Git actually does this:
    1. a new commit object is created, with the current branch’s ID as its parent;
    2. the commit object is hashed and stored;
    3. the branch ref is updated to refer to the new commit’s hash.
    
    But what about the current branch? It’s actually even easier. It’s a ref file outside of the refs hierarchy, in .git/HEAD, which is an indirect ref (that is, it is of the form ref: path/to/other/ref, and not a simple hash).
    """

    fmt = b'tag'


def ref_resolve(repo, ref):
    with open(repo_file(repo, ref), 'r') as fp:
        data = fp.read().rstrip()
        if data.startswith("ref: "):
            return ref_resolve(repo, data[5:])
        else:
            return data

            
def ref_list(repo, path=None):
    if not path:
        path = repo_find(repo, "refs")
    ret = collections.OrderedDict()
    
    for f in sorted(os.listdir(path)):
        can = os.path.join(path, f)
        if os.path.isdir(can):
            ret[f] = ref_list(repo, can)
        else:
            ret[f] = ref_resolve(repo, can)
    
    return ret


def ref_show(repo, refs, with_hash=True, prefix=""):
    for k, v in refs.items():
        if type(v) == str:
            print ("{0}{1}{2}".format(
                v + " " if with_hash else "",
                prefix + "/" if prefix else "",
                k))
        else:
            ref_show(repo, v, with_hash=with_hash, prefix="{0}{1}{2}".format(prefix, "/" if prefix else "", k))

            
def tag_create(name, obj, type):
    # TODO
    raise NotImplementedError()



        