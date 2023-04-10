use std::cmp::Ordering;
use std::path::Path;
use breezy_osutils::sha::{sha_file_by_name,sha_file};
use std::fs::File;
use std::fs::Metadata;

pub trait SHA1Provider {

    fn sha1(&self, path: &Path) -> std::io::Result<String>;

    fn stat_and_sha1(&self, path: &Path) -> std::io::Result<(Metadata, String)>;
}

/// A SHA1Provider that reads directly from the filesystem."""
pub struct DefaultSHA1Provider;

impl SHA1Provider for DefaultSHA1Provider {
    /// Return the sha1 of a file given its absolute path.
    fn sha1(&self, path: &Path) -> std::io::Result<String> {
        sha_file_by_name(path)
    }

    /// Return the stat and sha1 of a file given its absolute path.
    fn stat_and_sha1(&self, path: &Path) -> std::io::Result<(Metadata, String)> {
        let mut f = File::open(path)?;
        let stat = f.metadata()?;
        let sha1 = sha_file(&mut f)?;
        Ok((stat, sha1))
    }
}

pub fn lt_by_dirs(path1: &Path, path2: &Path) -> bool {
    let path1_parts = path1.components();
    let path2_parts = path2.components();
    let mut path1_parts_iter = path1_parts.into_iter();
    let mut path2_parts_iter = path2_parts.into_iter();

    loop {
        match (path1_parts_iter.next(), path2_parts_iter.next()) {
            (None, None) => return false,
            (None, Some(_)) => return true,
            (Some(_), None) => return false,
            (Some(part1), Some(part2)) => {
                match part1.cmp(&part2) {
                    Ordering::Equal => continue,
                    Ordering::Less => return true,
                    Ordering::Greater => return false,
                }
            }
        }
    }
}

pub fn lt_path_by_dirblock(path1: &Path, path2: &Path) -> bool {
    let key1 = (path1.parent(), path1.file_name());
    let key2 = (path2.parent(), path2.file_name());

    key1 < key2
}

pub fn bisect_path_left(paths: &[&Path], path: &Path) -> usize {
    let mut hi = paths.len();
    let mut lo = 0;
    while lo < hi {
        let mid = (lo + hi) / 2;
        // Grab the dirname for the current dirblock
        let cur = paths[mid];
        if lt_path_by_dirblock(cur, path) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    lo
}

pub fn bisect_path_right(paths: &[&Path], path: &Path) -> usize {
    let mut hi = paths.len();
    let mut lo = 0;
    while lo < hi {
        let mid = (lo + hi) / 2;
        // Grab the dirname for the current dirblock
        let cur = paths[mid];
        if lt_path_by_dirblock(path, cur) {
            hi = mid;
        } else {
            lo = mid + 1;
        }
    }
    lo
}
