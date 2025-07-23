# Language

Create language file with below data structure
* (Language Name)
  * property.json
  * (optional bin / image files)

For optional bin files, check out `data/bin_patch.json`.

---
## makediff.py

You can create bin files using contents below:
* [oot decompiler](https://github.com/zeldaret/oot)
* OOT rom (Recommend using ntsc-1.0 or mq-debug)

On `makediff.py`, you can see `make_diff`  
1. Set the original as the path of non-patched vannila OOT rom, set the replace as the path of patched one (edited one)  
2. Set the export as the ones on `data/bin_patch.json`, search the address within the name from [Filelist](https://wiki.cloudmodding.com/oot/File_List/NTSC_1.0)  
3. Copy the start / end address and type it down
4. Execute, and you'll have the bin file

---
## Font choice

The font that is used for texts would be ChiaroStd (キアロ Std) for normal texts,  
MatissePro B (マティス Pro B) for title texts
