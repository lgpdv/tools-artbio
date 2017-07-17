#!/usr/bin/env python
import optparse
from collections import defaultdict
import pysam
import sys

def option_parsing():
    parser = optparse.OptionParser(description='Count miRNAs')
    parser.add_option('-p', '--pre_mirs', action='store_true', dest='pre_mirs', help='Count pre-miRNAs', default=False)
    parser.add_option('-m', '--mirs', action='store_true', dest='mirs', help='Count mature miRNAs', default=False)
    inputs = optparse.OptionGroup(parser, 'Inputs')
    inputs.add_option('--alignment', type='string', dest='alignment_file', help='Alignment tabular or sam file')
    inputs.add_option('--gff', type='string', dest='gff_file', help='GFF3 describing both pre-miRNAs and mature miRNAs', metavar='FILE')
    inputs.add_option('--quality_threshold', type='int', dest='quality_threshold', help='Quality of the base alignment to take in to consideration when counting coverage (default=10)', default=10)
    inputs.add_option('--sample', type='string', dest='sample_name', help='Sample name (default= sample1)', default='sample1')
    parser.add_option_group(inputs)
    outputs = optparse.OptionGroup(parser, 'Outputs')
    outputs.add_option('--pre_mirs_output', type='string', dest='output_pre_mirs', help='Output file containing table containing the number of hits per pre-miRNA', metavar='FILE', default='output_pre_mirs_count.tab')
    outputs.add_option('--mature_mirs_output', type='string', dest='output_mature_mirs', help='Output file containing the number of hits per mature miRNA', metavar='FILE', default='output_mirs_count.tab')
    outputs.add_option('--lattice', type='string', dest='lattice', help="Output file for the lattice dataframe (if none given it won't be outputed)")
    parser.add_option_group(outputs)
    (options, args) = parser.parse_args()
    """ Check if the options were correctly passed """
    if len(args) > 0:
        parser.error('Please use the options flags to pass your arguments')
    if (not options.alignment_file or not options.gff_file):
        parser.error("Missing file. Both '--alignment' and '--gff' files are needed")
    return options

def get_pre_mir_counts(bamfile, quality_th):
    """
    Takes a AlignmentFile object and and returns a dictionary of dictionary
    with "count" key containing the count of reads aligning with the pre_mirs
    and "coverage" key containing a list of coverage along the coordinates of
    the pre_mirs
    """
    count = defaultdict(dict)
    reference_lengths = bamfile.lengths
    for ref_name, ref_len in zip(bamfile.references, reference_lengths):
        count[ref_name]["count"] = bamfile.count(ref_name)
        count[ref_name]["coverage"] = bamfile.count_coverage(
                                               reference=ref_name,
	                                           start=0, end=ref_len,
	                                           quality_threshold=quality_th)
        """ Add the 4 coverage values """
        count[ref_name]["coverage"] = [sum(x) for x
                                       in zip(*count[ref_name]["coverage"])]
    return count

def get_mir_counts(bamfile, gff_file, quality_th):
    """
    Takes a AlignmentFile and a gff file and computes for
    each 'miRNA' region of the gff the number of reads that hit it
    returns a dict[mir_name] = count
    """
    counts = dict()
    refs = bamfile.references
    for line in open(gff_file, 'r'):
        if line[0] != '#':
            gff_fields = line[:-1].split("\t")
            if gff_fields[2] == 'miRNA':
                mir_name = gff_fields[0]
                premir_name = gff_fields[8].split('Parent_mir_Name=')[1].split(';')[0]
                mir_start = int(gff_fields[3])
                mir_end = int(gff_fields[4])
                # GFF is 1-based, pysam is 0-based
                counts[mir_name] = dict()
                counts[mir_name]['count'] = bamfile.count(premir_name, mir_start-1, mir_end-1)
    return counts

def write_dataframe(mirs, outfile, sample):
    """
    Takes a dictionnary dict[reference name] = [count, [Hits of each position for 'A']]
    And prints a dataframe with columns: sample, mir, offset, offsetNorm, counts, countsNorm
    in the outfile
    """
    dataframe = []
    dataframe.append("sample\tmir\toffset\toffsetNorm\tcounts\tcountsNorm")
    for ref in sorted(mirs.keys()):
        """ For each reference name in mirs write the coverage of each of its positions """
        coverage_array = mirs[ref]["coverage"]
        reference_length = len(coverage_array)
        maximum = max(coverage_array)
        for pos in range(reference_length):
            """ Compute coverage of each position and append to the dataframe a new line"""
            coverage = coverage_array[pos]
            dataframe.append("\t".join([sample, ref,
                                        str(pos+1), # offset + 1 because range starts from 0
                                        str(float((pos+1))/reference_length), # offsetNorm
                                        str(coverage), # count
                                        str(float(coverage)/float(maximum)) if maximum >0 else '0'])) # countNorm
    try:
        out = open(outfile, 'w')
        out.write("\n".join(dataframe))
        out.write("\n")
        out.close()
    except IOError as e:
        sys.stderr.write("Error while writing file %s\n" % outfile)
        sys.stderr.write("I/O error(%s): %s\n" % (e.errno, e.strerror))

def write_counts(counts, outfile):
    """
    Takes a dictionary of counts[mir]=[counts] and prints it as a table of Gene Counts
    """
    table = []
    table.append("Gene\tCounts")
    for gene in counts:
        table.append("\t".join([gene, str(counts[gene]['count'])]))
    try:
        out = open(outfile, 'w')
        out.write("\n".join(table))
        out.write("\n")
        out.close()
    except IOError as e:
        sys.stderr.write("Error while writing file %s\n" % outfile)
        sys.stderr.write("I/O error(%s): %s\n" % (e.errno, e.strerror))

def __main__():
    options = option_parsing()
    bamfile = pysam.AlignmentFile(options.alignment_file, 'rb', check_sq=False)
    pre_mirs = dict()
    mirs = dict()
    if options.pre_mirs:
        pre_mirs = get_pre_mir_counts(bamfile, options.quality_threshold)
        write_counts(pre_mirs, options.output_pre_mirs)
        if options.lattice:
            write_dataframe(pre_mirs, options.lattice, options.sample_name)
    if options.mirs:
        mirs = get_mir_counts(bamfile, options.gff_file, options.quality_threshold)
        write_counts(mirs, options.output_mature_mirs)

if __main__():
    __main__()

