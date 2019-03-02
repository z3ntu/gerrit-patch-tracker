#!/usr/bin/python3

import re
import sys

import git
from pygerrit2 import GerritRestAPI

# Where the stock LineageOS repos get used for security patches
los_repos = [
    'android_external_chromium',
    'android_external_chromium_org_third_party_openssl',
    'android_external_expat',
    'android_external_freetype',
    'android_external_libnfc-nci',
    'android_external_libvorbis',
    'android_external_libxml2',
    'android_external_neven',
    'android_external_sfntly',
    'android_external_tremolo',
    'android_system_media'
]

# Ignore these repos (unused ones)
ignore_repos = [
    'android',
    'android_bootable_recovery',
    'android_bootable_recovery-cm',
    'android_hardware_qcom_audio',
    'android_hardware_qcom_audio-caf',
    'android_hardware_qcom_media',
    'android_hardware_qcom_media-caf',
    'android_kernel_samsung_jf',
    'android_kernel_samsung_smdk4412'
]

ignore_asb = [
    'asb-2017.07.05-cm-11.0'
]

ignore_changes = [
    143014, # Revert of non-existing commit
    127580, # Nfc: not used
    4776, 4775, 162887, 162888, # Dalvik: MTK removed files
    236196, 234632 # BT: 'HID Device Role' doesn't exist
]

def change_id_present(repo_name, change_id, los_merged):
    if repo_name in los_repos:
        return los_merged

    try:
        repo = git.Repo("/root/mtk-repos/" + repo_name, odbt=git.GitDB)
    except git.exc.NoSuchPathError:
        print("**WARNING: Failed to find repository: " + repo_name + " which is needed for applying this ASB!")
        return False

    head = None
    for rhead in repo.heads:
        if rhead.name == "mtk-4.4.4":
            head = rhead
            break
    if head is None:
        raise RuntimeError("Failed to find mtk-4.4.4 head!")

    chid_str = "Change-Id: " + change_id
    # iter_parents() below doesn't look at head.commit
    if chid_str in head.commit.message:
        return True

    for commit in head.commit.iter_parents():
        if chid_str in commit.message:
            return True
    return False


def main():
    print("Getting changes from Gerrit...", file=sys.stderr)

    query = "branch:cm-11.0"
    rest = GerritRestAPI(url='https://review.lineageos.org')
    changes = rest.get("/changes/?q={}".format(query))
    # Go through all pages (we only get 500 per request)
    while "_more_changes" in changes[-1]:
        newchanges = rest.get("/changes/?q={}&start={}".format(query, str(len(changes))))
        changes.extend(newchanges)
    print("Got {} changes...".format(len(changes)), file=sys.stderr)

    # Matches the many different topic names that were used over the years, see https://pastebin.com/raw/d4sSPihB
    asbre = re.compile(r"^(?:cm-11-)?asb-\d{4}\.\d{2}(?:\.\d{2})?(?:-cm11|-cm-11.0)?$")
    asb_dict = {}

    print("Filtering changes by topic...", file=sys.stderr)
    for change in changes:
        if "topic" in change:
            topic = change["topic"]
            if asbre.match(topic):
                if topic not in asb_dict:
                    asb_dict[topic] = []
                asb_dict[topic].append(change)

    print("Iterating through {} ASB topics...".format(len(asb_dict)), file=sys.stderr)
    merged = 0
    total = 0
    for asb, changes in sorted(asb_dict.items()):
        if asb in ignore_asb:
            continue
        print("*{}*\n".format(asb))
        for change in changes:
            if change["status"] == "ABANDONED":
                # print("Skipping abandoned change.")
                continue
            repo = change["project"].replace("LineageOS/", "")
            change_id = change["change_id"]
            # Ignore the repos in that list
            if repo in ignore_repos:
                continue
            # Ignore changes in that list
            if change["_number"] in ignore_changes:
                continue

            present = change_id_present(repo, change_id, change["status"] == "MERGED")
            if present:
                mystr = "- [x]"
                merged += 1
            else:
                mystr = "- [ ]"
            total += 1
            print("{} {} {}".format(mystr, change["_number"], repo))
        print()
    print("Merged: {} - Total: {}".format(merged, total))


if __name__ == '__main__':
    main()
