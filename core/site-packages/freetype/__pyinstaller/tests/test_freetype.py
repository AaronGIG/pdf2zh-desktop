def test_pyi_freetype(pyi_builder):
    pyi_builder.test_source(
        """
        import sys
        import pathlib

        import freetype

        # Ensure that the freetype shared library is bundled with the frozen
        # application; otherwise, freetype might be using system-wide library.

        # Check that freetype.FT_Library_filename is an absolute path;
        # otherwise, it is likely using basename-only ctypes fallback.
        ft_library_file = pathlib.Path(freetype.FT_Library_filename)
        print(f"FT library file (original): {ft_library_file}", file=sys.stderr)
        assert ft_library_file.is_absolute(), \
            "FT library file is not an absolute path!"

        # Check that fully-resolved freetype.FT_Library_filename is
        # anchored in fully-resolved frozen application directory.
        app_dir = pathlib.Path(__file__).resolve().parent
        print(f"Application directory: {app_dir}", file=sys.stderr)

        ft_library_path = pathlib.Path(ft_library_file).resolve()
        print(f"FT library file (resolved): {ft_library_path}", file=sys.stderr)

        assert app_dir in ft_library_path.parents, \
            "FT library is not bundled with frozen application!"
        """
    )
