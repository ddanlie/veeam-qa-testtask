# veeam-qa-testtask
Folder synchronization
Project was tested on python 3.11, windows 10 

## How to run
- Open folder with _sync.py_ file with command line
- Execute _python sync.py --help_

## Run test 
- Copy _source_ and _replica_ folders to the same directory as _sync.py_
- Execute _python sync.py -s ./source -d ./replica -l ./log.txt -p 5_

In log file you can see that _todelete.txt was renamed_ and _torename.txt was removed_
This happens because md5 sum of that files is the same (they are empty).
Such a permutation does not affect synchonization correctness, because every file in source folder is
considered exactly once


## tmp.patch
- Program creates temporary _tmp.patch_ file during execution

## Memory
- To be able to synchronize folders you need to have _free memory > source folder size * 2 - dst folder size_
