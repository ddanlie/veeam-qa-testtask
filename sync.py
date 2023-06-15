import bsdiff4 as diff
from  filecmp import dircmp
import sys
import os
import os.path as osp
import time
import hashlib
import shutil
import argparse


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src-path", "-s", nargs="?", required=True, metavar="src", help="Directory to synchronize with")
    parser.add_argument("--dst-path", "-d", nargs="?", required=True, metavar="dst", help="Directory where to do changes")
    parser.add_argument("--log-path", "-l", nargs="?", required=True, metavar="log", help="File where to write logs")
    parser.add_argument("--period", "-p", nargs="?", required=True, type=int, choices=range(1, 24*60*60), metavar="per", help="Time in seconds after which next synchonization happens")

    args = vars(parser.parse_args())
    
    return args

def get_md5(filename):
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def foldersize(foldername):
    size = 0
    for path, _, files in os.walk(foldername):
        for f in files:
            fp = osp.join(path, f)
            size += osp.getsize(fp)
    return size


class Synchronizer:

    def __init__(self, src_path, dst_path, log_path, period):
        self.src_path = osp.abspath(src_path)
        self.dst_path = osp.abspath(dst_path)
        self.log_path = log_path
        self.period = period


    def patch(self, from_path, to_path):
        diff.file_diff(to_path, from_path, "./tmp.patch")
        diff.file_patch_inplace(to_path, "./tmp.patch")

    #operation can be - remove, copy, create, rename
    def log(self, filename, operation, from_path, to_path):
        msg = f"File/Directory '{filename}' was "
        if(operation == "remove"):
            msg += f"removed from '{to_path}'"
        elif(operation == "copy"):
            msg += f"copied from '{from_path}' to '{to_path}'"
        elif(operation == "create"):
            msg += f"created in '{to_path}'"
        elif(operation == "rename"):
            msg += f"renamed in '{to_path}'"
        else:
            msg = ""
        with open(self.log_path, "a") as logfile:
            logfile.write(msg+"\n")
        print(msg)

    def synchronize_folders(self):
        if(osp.normpath(self.src_path) == osp.normpath(self.dst_path)):
            print("Same folder", file=sys.stderr)
            return 1
        
        while(True):
            #check folder sizes and system memory available
            #free memory > source_folder * 2 - dst_folder
            if(shutil.disk_usage(self.dst_path)[2] <= (foldersize(self.src_path) * 2) - foldersize(self.dst_path)):
                print("Not enough memory", file=sys.stderr)
                return 1

            dcmp = dircmp(self.src_path, self.dst_path)

            dir_full_paths = (self.src_path, self.dst_path)
            compares = [(dcmp, dir_full_paths)]
            
            #depth first search
            while len(compares) != 0:
                dcmp, dfp = compares.pop()#(dircmp, (src parent path, dst parent path)) pair
                src = dfp[0]
                dst = dfp[1]

                #Files with the same name - patch
                for f in dcmp.common_files:
                    srcf = osp.join(dst, f)
                    dstf = osp.join(src, f)
                    if(osp.getsize(srcf) != osp.getsize(dstf)):#probably modified
                        if(get_md5(srcf) != get_md5(dstf)):#definitely modified
                            self.patch(osp.join(src, f), osp.join(dst, f))
                            self.log(osp.join(src, f), "copy", src, dst)

                #Directories with the same name - recursively check (add to list)
                for dirname, dcmpobj in dcmp.subdirs.items():
                    compares.append((dcmpobj, (osp.join(src, dirname), osp.join(dst, dirname))))

                #Files/Dirs with different names - whether renamed, deleted or new
                tocopy_mask = [True for _ in range(len(dcmp.left_only))]
                for replica_file in dcmp.right_only:
                    replica_full_path = osp.join(dst, replica_file)
                    df = None
                    if(osp.isfile(replica_full_path)):
                        df = True
                    else:
                        df = False
                    deleted = True
                    for i, source_path in enumerate(dcmp.left_only):
                        source_full_path = osp.join(src, source_path)
                        df2 = None
                        if(osp.isfile(source_full_path)):
                            df2 = True
                        else:
                            df2 = False
                        if(df != df2):
                            continue
                        if(df and tocopy_mask[i]):#if tocopy_mask[i] = False, that means file/dir was already matched 
                            if(osp.getsize(replica_full_path) == osp.getsize(source_full_path)):#maybe file was renamed (quick pre-check)
                                if(get_md5(source_full_path) == get_md5(replica_full_path)):#file was renamed
                                    os.rename(replica_full_path, osp.join(dst, source_path))
                                    self.log(replica_full_path, "rename", src, dst)
                                    deleted = False
                                    tocopy_mask[i] = False
                        elif(tocopy_mask[i]):
                            #Blindly believe that same-size dirs are just renamed, but add them to "compares" list 
                            if(foldersize(replica_full_path) == foldersize(source_full_path)): #maybe dir was renamed, check instead deletion and copying
                                os.rename(replica_full_path, osp.join(dst, source_path))
                                self.log(replica_full_path, "rename", src, dst)
                                compares.append((dircmp(source_full_path, osp.join(dst, source_path)), (source_full_path, osp.join(dst, source_path))))
                                deleted = False
                                tocopy_mask[i] = False

                    if(deleted):
                        if(df):
                            os.remove(replica_full_path)#file was deleted - remove
                            self.log(replica_full_path, "remove", src, dst)
                        else:
                            shutil.rmtree(replica_full_path)#dir was deleted - remove
                            self.log(replica_full_path, "remove", src, dst)
                        
                #file/dir was created - copy
                for i, source_path in enumerate(dcmp.left_only):
                    source_full_path = osp.join(src, source_path)
                    if(tocopy_mask[i]):
                        if(osp.isfile(source_full_path)): 
                            shutil.copyfile(osp.join(src, source_path), osp.join(dst, source_path), follow_symlinks=False)
                        else:
                            shutil.copytree(osp.join(src, source_path), osp.join(dst, source_path))
                        self.log(osp.join(src, source_path), "copy", src, dst)
                    
            os.remove("./tmp.patch")
            print(f"Folder synchornized, next synchonization in {self.period} seconds")
            time.sleep(self.period)

        return 0


sync = Synchronizer(**get_args())
exit(sync.synchronize_folders())
