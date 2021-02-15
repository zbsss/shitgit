import os
import configparser


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
