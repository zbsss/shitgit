import argparse
import sys
from repository import *
from objects import *


def cmd_init(args):
    """Creates a new repository"""
    return repo_create(args.path)


def cat_file(repo, obj, fmt=None):
    """Prints a serialized git object"""
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())


def cmd_cat_file(args):
    """Prints a serialized git object"""
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())


def cmd_checkout(args):
    repo = repo_find()
    obj = object_read(repo, object_find(repo, args.commit))
    
    # if the object is a commit we grab it's tree
    if obj.fmt == b'commit':
        obj = object_read(repo, obj.msg[b'tree'].decode("ascii"))
    
    # verify that the path is an empty directory
    if os.path.exists(args.path):
        if not os.path.isdir(args.path):
            raise Exception(f"Not a directory {args.path}")
        elif os.listdir(args.path):
            raise Exception(f"Directory {args.path} not empty")
    else:
        os.makedirs(args.path)
    
    tree_checkout(repo, obj, os.path.realpath(args.path).encode())


def cmd_commit(args):
    pass


def cmd_hash_object(args):
    """Creates a git object from a file, prints it's hash"""
    if args.write:
        repo = repo_find('.')
    else:
        repo = None
    
    with open(args.path, 'rb') as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)


def cmd_log(args):
    repo = repo_find()
    print("digraph wyaglog{")
    log_graphviz(repo, object_find(repo, args.commit), set())
    print("}")


def cmd_ls_tree(args):
    repo = repo_find()
    tree = object_read(repo, object_find(repo, args.object, fmt=b'tree'))

    for entry in tree.entries:
        print("{0} {1} {2}\t{3}".format(
            "0" * (6 - len(entry.mode)) + entry.mode.decode("ascii"),
            # Git's ls-tree displays the type
            # of the object pointed to.  We can do that too :)
            object_read(repo, entry.sha).fmt.decode("ascii"),
            entry.sha,
            entry.path.decode("ascii")))

    

def cmd_merge(args):
    pass


def cmd_rebase(args):
    pass


def cmd_rev_parse(args):
    pass


def cmd_rm(args):
    pass


def cmd_show_ref(args):
    repo = repo_find()
    refs = ref_list(repo)
    show_ref(repo, refs, prefix="refs")


def show_ref(repo, refs, with_hash=True, prefix=""):
    for k, v in refs.items():
        if type(v) == str:
            print ("{0}{1}{2}".format(
                v + " " if with_hash else "",
                prefix + "/" if prefix else "",
                k))
        else:
            show_ref(repo, v, with_hash=with_hash, prefix="{0}{1}{2}".format(prefix, "/" if prefix else "", k))


def cmd_tag(args):
    repo = repo_find()

    if args.name:
        tag_create(args.name, args.object, 
                   type="object" if args.create_tag_object else "ref")
    


def cmd_add(args):
    pass


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


def parser_init():
    argparser = argparse.ArgumentParser(description="The stupid content tracker")

    argsubparser = argparser.add_subparsers(title="Commands", dest='command')
    argsubparser.required = True

    # shitgit init PATH
    argsp = argsubparser.add_parser("init", help="Initialize new repository")
    argsp.add_argument("path",
                    metavar="directory",
                    nargs="?",
                    default=".",
                    help="Where to create the repository.")

    # shitgit cat-file TYPE OBJECT
    argsp = argsubparser.add_parser("cat-file",
                                    help="Provide content of repository objects")
    argsp.add_argument("type",
                    metavar="type",
                    choices=["blob", "commit", "tag", "tree"],
                    help="Specify the type")
    argsp.add_argument("object",
                    metavar="object",
                    help="The object to display")

    # shitgit hash-object [-w] [-t TYPE] FILE
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
    
    # shitgit log HASH
    argsp = argsubparser.add_parser("log", help="Display history of a given commit.")
    argsp.add_argument("commit",
                   default="HEAD",
                   nargs="?",
                   help="Commit to start at.")

    # shitgit ls-tree
    argsp = argsubparser.add_parser("ls-tree", help="Pretty-print a tree object.")
    argsp.add_argument("object",
                    help="The object to show.")
    
    # shitgit checkout
    argsp = argsubparser.add_parser(
        "checkout", help="Checkout a commit inside of a directory.")
    argsp.add_argument("commit",
                    help="The commit or tree to checkout.")
    argsp.add_argument("path",
                    help="The EMPTY directory to checkout on.")


    # shitgit show-ref
    argsp = argsubparser.add_parser("show-ref", help="List references.")


    # shitgit tag
    argsp = argsubparser.add_parser(
    "tag",
    help="List and create tags")

    argsp.add_argument("-a",
                        action="store_true",
                        dest="create_tag_object",
                        help="Whether to create a tag object")

    argsp.add_argument("name",
                        nargs="?",
                        help="The new tag's name")

    argsp.add_argument("object",
                        default="HEAD",
                        nargs="?",
                        help="The object the new tag will point to")

    return argparser


def main(argv=sys.argv[1:]):
    argparser = parser_init()
    args = argparser.parse_args(argv)
    commands[args.command](args)
