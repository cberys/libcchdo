"""Common operations for zip data formats.

"""
import zipfile
from datetime import datetime
from tempfile import SpooledTemporaryFile

from libcchdo.log import LOG
from libcchdo import StringIO


class MemZipFile(zipfile.ZipFile):
    """A modified ZipFile that operates in memory. 
       Handy for writing zip files to streams that can't be seeked.
    """
    def __init__(self, handle, *args, **kwargs):
        self._handle = handle
        self._mem = StringIO()
        zipfile.ZipFile.__init__(self, self._mem, *args, **kwargs)

    def close(self):
        return_value = zipfile.ZipFile.close(self)
        try:
            self._handle.write(self._mem.getvalue())
            self._mem.close()
            del self._mem
        except AttributeError:
            pass
        except ValueError:
            pass
        return return_value


_zf_EndRecData = zipfile._EndRecData
class ZeroCommentZipFile(zipfile.ZipFile):
    """Hacked ZipFile that ignores zero length valid comment error.

    Related:
    http://bugs.python.org/issue1757072
    http://hg.python.org/cpython/rev/cc3255a707c7/

    This is useful up to and including 2.7.2 and 3.2 to ignore malformed zip
    files generated by OS X.

    """
    @staticmethod
    def _zero_length_valid_comment(fpin):
        """Determine whether the zipfile has a zero length valid comment.

        """

        import struct
        from zipfile import (
            sizeEndCentDir, stringEndArchive, structEndArchive, _ECD_OFFSET,
            _EndRecData64, _ECD_COMMENT_SIZE, stringCentralDir, 
        )

        # Determine file size
        fpin.seek(0, 2)
        filesize = fpin.tell()

        # Either this is not a ZIP file, or it is a ZIP file with an archive
        # comment.  Search the end of the file for the "end of central
        # directory" record signature. The comment is the last item in the ZIP
        # file and may be up to 64K long.  It is assumed that the "end of
        # central directory" magic number does not appear in the comment.
        maxCommentStart = max(filesize - (1 << 16) - sizeEndCentDir, 0)
        fpin.seek(maxCommentStart, 0)
        data = fpin.read()
        start = data.rfind(stringEndArchive)
        if start >= 0:
            # found the magic number; attempt to unpack and interpret
            recData = data[start:start+sizeEndCentDir]
            endrec = list(struct.unpack(structEndArchive, recData))
            comment = data[start+sizeEndCentDir:]

            # Here is where the fudging happens.
            fpin.seek(endrec[6], 0)
            dat = fpin.read(4)
            if endrec[_ECD_COMMENT_SIZE] == 0 and dat == stringCentralDir:
                # Append the archive comment and start offset
                endrec.append(comment)
                endrec.append(maxCommentStart + start)
                if endrec[_ECD_OFFSET] == 0xffffffff:
                    # There is apparently a "Zip64 end of central directory"
                    # structure present, so go look for it
                    return _EndRecData64(fpin, start - filesize, endrec)
                return endrec

        # Unable to find a valid end of central directory structure
        return

    def _RealGetContents(self):
        """Override to ignore zero length valid comments.

        This problem exists up to and including 2.7.2 and 3.2.

        """
        super_RealGetContents = zipfile.ZipFile._RealGetContents
        try:
            return super_RealGetContents(self)
        except zipfile.BadZipfile:
            zipfile._EndRecData = self._zero_length_valid_comment
            try:
                return super_RealGetContents(self)
            finally:
                zipfile._EndRecData = _zf_EndRecData


def create(handle):
    try:
        return MemZipFile(handle, 'w', zipfile.ZIP_DEFLATED)
    except RuntimeError:
        LOG.info(
            u'Unable to write deflated zip file. Using store algorithm '
            'instead.')
        return MemZipFile(handle, 'w')


def createZipInfo(filename, dtime=None, permissions=0644):
    """Create a ZipInfo for a filename.

    Arguments::
    dtime - date time to use for the file. (default: now)
    permissions - permissions to use for the file (default: 0644)

    """
    if dtime is None:
        dtime = datetime.now()

    info = zipfile.ZipInfo(filename)
    info.date_time = (dtime.year, dtime.month, dtime.day,
                      dtime.hour, dtime.minute, dtime.second)
    info.external_attr = permissions << 16L
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def write(self, handle, writer, get_filename):
    """Common write functionality for zip files."""
    zfile = create(handle)
    for dfile in self:
        with SpooledTemporaryFile(max_size=2 ** 13) as tempfile:
            writer.write(dfile, tempfile)
            tempfile.flush()
            tempfile.seek(0)

            filename = get_filename(dfile)
            try:
                zfile.writestr(createZipInfo(filename), tempfile.read())
            except Exception, err:
                LOG.error(u'Unable to write {0}: {1!r}'.format(filename, err))
    zfile.close()
