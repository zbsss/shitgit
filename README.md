Based on https://wyag.thb.lt/#orge011130

---
### Notes:

To make shitgit run as a terminal command, the `shitgit` file has to be moved to `/usr/local/bin/` and a path to the project folder has to be added to sysem path variable so that shitgitlib can be imported. 

```python
#!/usr/bin/env python3

import sys
sys.path.append('/home/zbsss/Desktop/shitgit')

import shitgitlib
shitgitlib.main()
```