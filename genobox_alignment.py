#!/usr/bin/python

def check_fa(fa):
   '''Checks for a fa of the input fasta file. If not present creates it'''
   
   import genobox_moab
   import subprocess
   import os
   import sys
   
   paths = genobox_moab.setSystem()
   
   # check if fa exists
   index_suffixes = ['.amb', '.ann', '.bwt', '.pac', '.rbwt', '.rpac', '.rsa', '.sa']
   for suf in index_suffixes:
      f = fa + suf
      if os.path.exists(f):
         pass
      else:
         sys.stderr.write('%s not found, creating bwa index\n' % fa)
         call = paths['bwa_home'] + 'bwa index -a is %s' % fa
         try: 
            subprocess.check_call(call, shell=True)
         except:
            sys.stderr.write('bwa index -a is failed, trying bwa index -a bwtsw\n')
            call = paths['bwa_home'] + 'bwa index -a bwtsw %s' % fa
            try:
               subprocess.check_call(call, shell=True)
            except: 
               raise TypeError('bwa index could not be created from %s' % fa)
         break
 

def check_formats_fq(i):
   '''Checks format of fastq file and returns it'''
   
   import genobox_modules
   
   # check if fastq and if so mode
   format = genobox_modules.set_filetype(i)
   if format != 'fastq':
      raise ValueError('Input must be fastq')
   else:
      fqtype = genobox_modules.set_fqtype(i)   
   return fqtype


def all_same(items):
   '''Check if all items in list/tuple are the same type'''
   return all(x == items[0] for x in items)


def bwa_se_align(fastqs, fa, fqtypes, qtrim, alignpath, libdict, threads, queue, logger):
   '''Start alignment using bwa of fastq reads on index'''
   
   import subprocess
   import genobox_moab
   import genobox_modules
   import os
   paths = genobox_moab.setSystem()
   home = os.getcwd()
   
   # setting cpus
   cpuA = 'nodes=1:ppn=1,mem=5gb'
   cpuC = 'nodes=1:ppn=1,mem=2gb'
   if threads != 1:
      cpuB = 'nodes=1:ppn=%s,mem=5gb' % threads
   else:
      cpuB = cpuA
   
   # get readgroups
   RG = genobox_modules.read_groups_from_libfile('Data', libdict)
   
   # align
   cmd = paths['bwa_home'] + 'bwa'
   bwa_align = []
   saifiles = []
   for i,fq in enumerate(fastqs):
      f = os.path.split(fq)[1]
      saifile = alignpath + f + '.sai'
      saifiles.append(saifile)
      if fqtypes[i] == 'Illumina':
         arg = ' aln -I -t %i -q %i %s %s > %s' % (threads, qtrim, fa, fq, saifile)
      elif fqtypes[i] == 'Sanger':
         arg = ' aln -t %i -q %i %s %s > %s' % (threads, qtrim, fa, fq, saifile)   
      bwa_align.append(cmd+arg)
   
   # samse
   bwa_samse = []
   bamfiles = []
   bamfiles_dict = dict()
   for i,fq in enumerate(fastqs):
      f = os.path.split(fq)[1]
      bamfile = alignpath + f + '.bam'
      bamfiles.append(bamfile)
      bamfiles_dict[fq] = bamfile
      call = '%sbwa samse -r \"%s\" %s %s %s | %ssamtools view -Sb - > %s' % (paths['bwa_home'], '\\t'.join(RG[fq]), fa, saifiles[i], fq, paths['samtools_home'], bamfile)
      bwa_samse.append(call)
      
   # submit jobs
   allids = []
   
   bwa_alignids = genobox_moab.submitjob(bwa_align, home, paths, logger, 'run_genobox_bwaalign', queue, cpuB, False)
   bwa_samseids = genobox_moab.submitjob(bwa_samse, home, paths, logger, 'run_genobox_bwasamse', queue, cpuA, True, 'one2one', 1, True, *bwa_alignids)
   
   allids.extend(bwa_alignids) ; allids.extend(bwa_samseids)
   
   # release jobs
   releasemsg = genobox_moab.releasejobs(allids)
   
   return (bwa_samseids, bamfiles_dict)

def bwa_pe_align(pe1, pe2, fa, fqtypes_pe1, fqtypes_pe2, qtrim, alignpath, a, libdict, threads, queue, logger):
   '''Start alignment using bwa of paired end fastq reads on index'''
   
   import subprocess
   import genobox_moab
   import genobox_modules
   import os
   paths = genobox_moab.setSystem()
   home = os.getcwd()
   
   # setting cpus
   cpuA = 'nodes=1:ppn=1,mem=5gb'
   cpuC = 'nodes=1:ppn=1,mem=2gb'
   if threads != 1:
      cpuB = 'nodes=1:ppn=%s,mem=5gb' % threads
   else:
      cpuB = cpuA
   
   # get readgroups
   RG = genobox_modules.read_groups_from_libfile('Data', libdict)
   
   # align and sampe
   cmd = paths['bwa_home'] + 'bwa'
   bwa_align = []
   sam2bam_calls = []
   bwa_align1_calls = []
   bwa_align2_calls = []
   bwa_sampe_calls = []
   
   saifiles1 = []
   saifiles2 = []
   bamfiles = []
   bamfiles_dict = dict()
   
   for i,fq in enumerate(pe1):
      # set input fastq format
      if fqtypes_pe1[i] != fqtypes_pe2[i]:
         raise ValueError('Fastq formats are not the same for %s and %s' % (pe1[i], pe2[i]))
      elif fqtypes_pe1[i] == 'Sanger':
         bwa_cmd = '%sbwa aln ' % paths['bwa_home']
      elif fqtypes_pe1[i] == 'Illumina':
         bwa_cmd = '%sbwa aln -I ' % paths['bwa_home']
      else:
         raise ValueError('fqtype must be Sanger or Illumina')
      
      # set filenames
      f1 = os.path.split(pe1[i])[1]
      f2 = os.path.split(pe2[i])[1]
      saifile1 = alignpath + f1 + '.sai'
      saifile2 = alignpath + f2 + '.sai'
      saifiles1.append(saifile1)
      saifiles2.append(saifile2)
      bamfiles.append(alignpath + f1 + '.bam')
      
      bamfiles_dict[pe1[i]] = alignpath + f1 + '.bam'
      bamfiles_dict[pe2[i]] = alignpath + f1 + '.bam'
      
      # generate calls
      bwa_align1 = '%s -t %s -q %i %s -f %s %s ' % (bwa_cmd, threads, qtrim, fa, saifiles1[i], pe1[i])
      bwa_align2 = '%s -t %s -q %i %s -f %s %s ' % (bwa_cmd, threads, qtrim, fa, saifiles2[i], pe2[i])
      sampecall = '%sbwa sampe -a %i -r \"%s\" %s %s %s %s %s | %ssamtools view -Sb - > %s' % (paths['bwa_home'], a, '\\t'.join(RG[fq]), fa, saifiles1[i], saifiles2[i], pe1[i], pe2[i], paths['samtools_home'], bamfiles[i])
      bwa_align1_calls.append(bwa_align1)
      bwa_align2_calls.append(bwa_align2)
      bwa_sampe_calls.append(sampecall)
      
   
   # submit jobs
   allids = []
   bwa_alignids1 = genobox_moab.submitjob(bwa_align1_calls, home, paths, logger, 'run_genobox_bwaalign1', queue, cpuB, False)
   bwa_alignids2 = genobox_moab.submitjob(bwa_align2_calls, home, paths, logger, 'run_genobox_bwaalign2', queue, cpuB, False)
   
   # set jobids in the correct way
   bwa_alignids = []
   for i in range(len(bwa_alignids1)):
      bwa_alignids.append(bwa_alignids1[i])
      bwa_alignids.append(bwa_alignids2[i])
   
   # submit sampe
   bwa_sampeids = genobox_moab.submitjob(bwa_sampe_calls, home, paths, logger, 'run_genobox_bwasampe', queue, cpuA, True, 'conc', len(bwa_alignids)/2, True, *bwa_alignids)
   
   # release jobs
   allids.extend(bwa_alignids) ; allids.extend(bwa_sampeids)
   releasemsg = genobox_moab.releasejobs(allids)
   
   return (bwa_sampeids, bamfiles_dict)
   

def start_alignment(args, logger):
   '''Start alignment of fastq files using BWA'''
   
   import genobox_moab
   import genobox_modules
   import subprocess
   import os
   
   paths = genobox_moab.setSystem()
   home = os.getcwd()
   semaphore_ids = []
   bamfiles = dict()
   
   if not os.path.exists('alignment'):
      os.makedirs('alignment')
   
   # check and load/create library file
   if args.libfile and args.libfile != 'None':
      libdict = genobox_modules.read_library(args.libfile)
      libfile = args.libfile
   else:
      try:
         (libdict, libfile) = genobox_modules.library_from_input(args.se + args.pe1 + args.pe2, args.sample, args.mapq, args.libs)
      except:
         (libdict, libfile) = genobox_modules.library_from_input(args.se + args.pe1 + args.pe2, args.sample, [30], args.libs)
   
   # check for fa
   check_fa(args.fa)
   
   # start single end alignments
   if args.se:
      
      # set fqtypes
      fqtypes_se = map(check_formats_fq, args.se)
      print "Submitting single end alignments"
      (se_align_ids, bamfiles_se) = bwa_se_align(args.se, args.fa, fqtypes_se, args.qtrim, 'alignment/', libdict, args.n, args.queue, logger)
      semaphore_ids.extend(se_align_ids)
      bamfiles.update(bamfiles_se)
      
   # start paired end alignments
   if args.pe1:
      if len(args.pe1) != len(args.pe2):
         raise ValueError('Same number of files must be given to --pe1 and --pe2')
            
      # set fqtypes
      fqtypes_pe = []
      fqtypes_pe1 = map(check_formats_fq, args.pe1)
      fqtypes_pe2 = map(check_formats_fq, args.pe2)
      fqtypes_pe.extend(fqtypes_pe1)
      fqtypes_pe.extend(fqtypes_pe2)
      
      print "Submitting paired end alignments"
      (pe_align_ids, bamfiles_pe) = bwa_pe_align(args.pe1, args.pe2, args.fa, fqtypes_pe1, fqtypes_pe2, args.qtrim, 'alignment/', args.a, libdict, args.n, args.queue, logger)            
      semaphore_ids.extend(pe_align_ids)
      bamfiles.update(bamfiles_pe)

   # update libfile
   genobox_modules.update_libfile(libfile, 'Data', 'BAM', bamfiles, force=True)
   
   # wait for jobs to finish
   print "Waiting for jobs to finish ..." 
   genobox_moab.wait_semaphore(semaphore_ids, home, 'bwa_alignment', args.queue, 60, 86400)
   print "--------------------------------------"
   
   
   # return bamfiles   
   return (bamfiles, libfile)
