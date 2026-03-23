import chalk from 'chalk';
import { table } from 'table';
import { Searcher } from '../services/Searcher.js';
import { ConfigManager } from '../config/index.js';

const CLOUD_TYPE_NAMES = {
  pan115: '115网盘',
  aliyun: '阿里云盘',
  quark: '夸克网盘',
  baidu: '百度网盘',
  tianyi: '天翼云盘',
  pan123: '123云盘',
  unknown: '未知',
};

function getCloudTypeColor(type) {
  const colors = {
    pan115: chalk.red.bold('115网盘'),
    aliyun: chalk.blue.bold('阿里云盘'),
    quark: chalk.yellow.bold('夸克网盘'),
    baidu: chalk.cyan.bold('百度网盘'),
    tianyi: chalk.magenta.bold('天翼云盘'),
    pan123: chalk.green.bold('123云盘'),
    unknown: chalk.gray('未知'),
  };
  return colors[type] || type;
}

export function searchCommand(program) {
  program
    .command('search <keyword>')
    .alias('s')
    .description('搜索网盘资源')
    .option('-l, --limit <number>', '限制结果数量', '20')
    .option('--no-table', '不使用表格格式输出')
    .action(async (keyword, options) => {
      try {
        const config = ConfigManager.load();

        if (config.search.channels.length === 0) {
          console.log(chalk.yellow('⚠️  请先配置搜索频道:'));
          console.log(chalk.cyan('  cloudsaver-cli config --add-channel'));
          return;
        }

        console.log(chalk.blue(`🔍 正在搜索: "${keyword}"...`));
        console.log(chalk.gray(`📡 搜索 ${config.search.channels.length} 个频道...\n`));

        const searcher = new Searcher();
        const results = await searcher.searchAll(keyword, config.search.channels);

        if (results.length === 0) {
          console.log(chalk.yellow('❌ 未找到相关资源'));
          return;
        }

        const limit = Number.parseInt(options.limit, 10) || 20;
        const limited = results.slice(0, limit);

        console.log(
          chalk.green(`✅ 找到 ${results.length} 个资源${results.length > limit ? `，显示前 ${limit} 个` : ''}\n`),
        );

        if (options.table !== false) {
          const tableData = [
            ['序号', '名称', '网盘', '链接', '频道', '时间'].map((header) => chalk.bold(header)),
            ...limited.map((item, index) => {
              const firstLink = item.cloudLinks[0];
              return [
                String(index + 1),
                item.title.length > 20 ? `${item.title.substring(0, 20)}...` : item.title,
                CLOUD_TYPE_NAMES[firstLink.type] || firstLink.type,
                firstLink.url.length > 35 ? `${firstLink.url.substring(0, 35)}...` : firstLink.url,
                item.channel,
                new Date(item.pubDate).toLocaleDateString(),
              ];
            }),
          ];

          console.log(table(tableData, {
            border: {
              topBody: '─',
              topJoin: '┬',
              topLeft: '┌',
              topRight: '┐',
              bottomBody: '─',
              bottomJoin: '┴',
              bottomLeft: '└',
              bottomRight: '┘',
              bodyLeft: '│',
              bodyRight: '│',
              bodyJoin: '│',
              joinBody: '─',
              joinLeft: '├',
              joinRight: '┤',
              joinJoin: '┼',
            },
          }));

          console.log(`\n${chalk.bold('📋 链接详情:')}`);
          limited.forEach((item, index) => {
            console.log(`\n${chalk.bold(`${index + 1}. ${item.title}`)}`);
            item.cloudLinks.forEach((link, linkIndex) => {
              console.log(`   ${linkIndex + 1}) ${getCloudTypeColor(link.type)}: ${chalk.underline(link.url)}`);
            });
          });
        } else {
          limited.forEach((item, index) => {
            console.log(chalk.bold(`${index + 1}. ${item.title}`));
            console.log(`   频道: ${item.channel} | 时间: ${new Date(item.pubDate).toLocaleString()}`);
            item.cloudLinks.forEach((link, linkIndex) => {
              console.log(`   ${linkIndex + 1}) ${getCloudTypeColor(link.type)}: ${link.url}`);
            });
            console.log();
          });
        }

        const has115 = limited.some((item) => item.cloudLinks.some((link) => link.type === 'pan115'));
        if (has115) {
          console.log(chalk.cyan('\n💡 提示: 使用 `cloudsaver-cli save` 命令可以转存115网盘资源'));
        }
      } catch (error) {
        console.error(chalk.red('搜索失败:'), error);
        process.exit(1);
      }
    });
}
