#!/usr/bin/env python3

import hashlib, json, os, util
from contest import Contest
from oier import OIer
from record import Record
from school import School
from sys import argv, stderr

def __main__():
	gender_map = {'男': 1, '女': -1}

	def parse_school_line(line):
		'''解析 school.txt 文件的一行。

		line: 一行。
		'''

		if line.startswith('#'): # 注释
			return
		li = line.split(',')
		if len(li) < 3:
			raise ValueError('格式错误')
		province, city, name, *aliases = li
		School.create(name, province, city, aliases)

	def parse_school():
		'解析 school.txt 文件。'

		with open('data/school.txt') as f:
			raw_data = f.readlines()
		for idx, line in enumerate(raw_data):
			try:
				parse_school_line(line.strip())
			except ValueError as e:
				print('\x1b[01mschool.txt:{}: \x1b[031merror: \x1b[0;37m\'{}\'\x1b[0m，{}'.format(idx + 1, line.strip(), e), file = stderr)

	def parse_raw_line(line):
		'''解析 raw.txt 文件的一行。

		line: 一行。
		'''

		if line.startswith('#'): # 注释
			return
		li = line.split(',')
		if len(li) != 9:
			raise ValueError('格式错误')
		contest_name, level, name, grade_name, school_name, score, province, gender_name, identifier = li
		if name == '':
			raise ValueError('姓名不能为空')
		contest = Contest.by_name(contest_name)
		school = School.by_name(school_name)
		grades = util.get_grades(grade_name)
		gender = gender_map.get(gender_name, 0)
		if not Contest.is_score_valid(score):
			raise ValueError('无法识别的分数：\x1b[032m\'{}\'\x1b[0m'.format(score))
		# 开始创建数据
		oier = OIer.of(name, identifier)
		record = contest.add_contestant(oier, score, level, grades, school, province, gender)
		oier.add_record(record)

	def parse_raw():
		'解析 raw.txt 文件。'

		with open('data/raw.txt') as f:
			raw_data = f.readlines()
		for idx, line in enumerate(raw_data):
			try:
				parse_raw_line(line.strip())
			except ValueError as e:
				print('\x1b[01mraw.txt:{}: \x1b[31merror: \x1b[0;37m\'{}\'\x1b[0m，{}'.format(idx + 1, line.strip(), e), file = stderr)

	def attempt_merge(threshold = 240):
		''' 尝试合并信息。

		threshold: 距离阈值。
		'''

		recordseqs = []
		length = OIer.count_all()
		for idx, oier in enumerate(OIer.get_all()):
			if idx % 1000 == 0:
				print('\r\x1b[2K{}% ...'.format(idx * 100 // length), end = '')
			# 手动合并的无需拆分
			if oier.identifier:
				recordseqs.append(oier.records)
				continue
			original_length = len(oier.records)
			a = [[record] for record in oier.records]
			while True:
				n, best, bi, bj = len(a), threshold + 1, -1, -1
				for i in range(n):
					for j in range(i):
						if (dist := Record.distance(a[j], a[i], threshold + 1)) < best:
							best, bi, bj = dist, j, i
				if best <= threshold:
					a[bi].extend(a[bj])
					del a[bj]
				else:
					break
			if '--show-incomplete-merge' in argv and len(a) != 1:
				print('\x1b[01;33mwarning: \x1b[0;32m\'{}\'\x1b[0m 未完全合并，合并进度为 \x1b[32m{}\x1b[0m → \x1b[32m{}\x1b[0m'.format(oier.name, original_length, len(a)), file = stderr)
			recordseqs.extend(a)
		OIer.clear()
		for recordseq in recordseqs:
			original = recordseq[0].oier
			# UID 定为该 OIer 首次出现的<b>有效</b>行号
			uid = min(recordseq, key = lambda record: record.id).id
			# 入学年份取众数，相同的话取最早的
			em = util.get_mode([record.ems for record in recordseq])[0]
			# 性别如果唯一则取之，空或不唯一置空（如跨性别）
			gender = set(record.gender for record in recordseq if record.gender)
			gender = gender.pop() if len(gender) == 1 else 0
			oier = OIer(original.name, original.identifier, gender, em, uid)
			oier.records = recordseq[:]
			for record in oier.records:
				record.oier = oier
		print()

	def analyze_individual_oier():
		'分析各体信息。'

		for oier in OIer.get_all():
			oier.compute_ccf_level()
			oier.compute_oierdb_score()

	def output_schools():
		'输出学校信息。'

		output = []
		for school in School.get_all():
			output.append([school.name, school.province, school.city, float(round(school.score, 2))])
		with open('data/school.json', 'w') as f:
			json.dump(output, f, ensure_ascii = False)

	def output_compressed():
		'输出压缩的结果，不压缩的结果先咕着。'

		OIer.sort_by_score()
		with open('data/result.txt', 'w') as f:
			for oier in OIer.get_all():
				print(oier.to_compress_format(), file = f)

	def compute_sha512():
		'''
		计算 data/result.txt 的 SHA512 值，保存在 sha512/result 中。
		（注：使用 *.txt 后缀可以利用 gzip 压缩）
		'''

		with open('data/result.txt', 'rb') as f:
			sha512 = hashlib.sha512(f.read()).hexdigest()
		with open('sha512/result', 'w') as f:
			print(sha512, file = f)

	def update_static():
		'调用 update_static.js 以产生静态 JSON 信息。'
		os.system('./update_static.js')

	def report_status(message):
		'向终端报告当前进度。'

		print('================ {} ================'.format(message), file = stderr)

	report_status('读取学校信息中')
	parse_school()

	report_status('读取选手信息中')
	parse_raw()

	report_status('合并信息中')
	attempt_merge()

	report_status('分析选手中')
	analyze_individual_oier()

	report_status('输出到 data/result.txt 中')
	output_compressed()

	report_status('计算 SHA512 摘要中')
	compute_sha512()

	report_status('输出学校信息中')
	output_schools()

	report_status('输出静态 JSON 信息中')
	update_static()

if __name__ == '__main__':
	__main__()
