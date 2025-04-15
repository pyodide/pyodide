# mypy: ignore-errors

import pathlib

from pytest_pyodide.decorator import run_in_pyodide

DEMO_PATH = pathlib.Path(__file__).parent / "test_data"
EX1_BAM = open(DEMO_PATH / "ex1.bam", "rb").read()

EX1_BAI = open(DEMO_PATH / "ex1.bam.bai", "rb").read()


def test_pysam(selenium):
    @run_in_pyodide(packages=["pysam"])
    def _test_pysam_inner(selenium, bam_file, index_file):
        import pysam

        # Write the BAM file to the filesystem
        with open("ex1.bam", "wb") as f:
            f.write(bam_file)

        # Write the BAM file to the filesystem
        with open("ex1.bam.bai", "wb") as f:
            f.write(index_file)

        # Open the BAM file for reading
        with pysam.AlignmentFile("ex1.bam", "rb") as samfile:
            # Assert contig names
            contig_names = list(samfile.references)
            assert contig_names == [
                "seq1",
                "seq2",
            ], "Contig names do not match expected values"

            # Fetch reads for a specific region and assert non-emptiness
            reads = list(samfile.fetch("seq1", 0, 100000))
            assert len(reads) > 0, "No reads fetched for region 'seq1'"

            # Test read attributes
            for read in reads:
                assert read.query_name is not None, "Read does not have a query name"
                assert read.query_sequence is not None, (
                    "Read does not have a query sequence"
                )
                assert read.flag is not None, "Read does not have a flag"

            # Count reads and assert correct number
            count = sum(1 for _ in samfile)
            assert count > 0, "Read count is not greater than 0"

            # Verify alignment statistics
            stats = samfile.get_index_statistics()
            assert all(stat.mapped > 0 for stat in stats), (
                "Some contigs have no mapped reads"
            )

    _test_pysam_inner(selenium, EX1_BAM, EX1_BAI)
