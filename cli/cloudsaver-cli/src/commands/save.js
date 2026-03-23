import chalk from 'chalk';
import inquirer from 'inquirer';
import { Cloud115Service } from '../services/Cloud115Service.js';

function formatFileSize(bytes) {
  if (bytes === 0) {
    return '0 B';
  }

  const unit = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.floor(Math.log(bytes) / Math.log(unit));
  return `${Number.parseFloat((bytes / (unit ** index)).toFixed(2))} ${sizes[index]}`;
}

export function saveCommand(program) {
  program
    .command('save [url]')
    .alias('sv')
    .description('转存115网盘资源')
    .option('-f, --folder <id>', '指定目标文件夹ID')
    .action(async (url, options) => {
      try {
        const service = new Cloud115Service();

        if (!service.hasCookie()) {
          console.log(chalk.yellow('⚠️  请先设置115网盘Cookie:'));
          console.log(chalk.cyan('  cloudsaver-cli config --set-cookie'));
          return;
        }

        let shareUrl;

        if (url) {
          if (!url.match(/(?:115|115cdn|anxia)\.com\/s\//)) {
            console.log(chalk.red('❌ 无效的115分享链接'));
            return;
          }
          shareUrl = url;
        } else {
          const answer = await inquirer.prompt([
            {
              type: 'input',
              name: 'url',
              message: '请输入115分享链接:',
              validate: (input) => {
                if (!input.match(/(?:115|115cdn|anxia)\.com\/s\//)) {
                  return '请输入有效的115分享链接';
                }
                return true;
              },
            },
          ]);
          shareUrl = answer.url;
        }

        console.log(chalk.blue('\n🔗 解析分享链接...'));
        const { shareCode, receiveCode } = service.parseShareUrl(shareUrl);

        const files = await service.getShareInfo(shareCode, receiveCode || '');
        if (files.length === 0) {
          console.log(chalk.yellow('⚠️  分享中没有文件'));
          return;
        }

        console.log(chalk.green(`✅ 找到 ${files.length} 个文件:\n`));
        files.forEach((file, index) => {
          console.log(`  ${index + 1}. ${file.fileName} (${formatFileSize(file.fileSize)})`);
        });

        let targetFolderId;
        let targetFolderName;

        if (options.folder) {
          targetFolderId = options.folder;
          targetFolderName = `指定文件夹 (${options.folder})`;
        } else {
          console.log(chalk.blue('\n📁 检查目标文件夹...'));
          targetFolderId = await service.ensureTransferFolder();
          targetFolderName = targetFolderId === '0' ? '根目录' : '转存';

          if (targetFolderId === '0') {
            console.log(chalk.yellow('⚠️  无法确认“转存”文件夹，已回退到根目录'));
          }
        }

        console.log(chalk.blue(`\n💾 开始转存到 "${targetFolderName}"...`));

        for (const file of files) {
          process.stdout.write(`  正在转存: ${file.fileName}... `);

          const result = await service.saveFile(
            shareCode,
            file.fileId,
            receiveCode || '',
            targetFolderId,
          );

          if (result.success) {
            console.log(chalk.green('✅ 成功'));
          } else {
            console.log(chalk.red(`❌ 失败 - ${result.message}`));
          }
        }

        console.log(chalk.green('\n✅ 转存完成!'));
      } catch (error) {
        console.error(chalk.red('\n❌ 转存失败:'), error.message || error);

        if (error.message?.includes('登录')) {
          console.log(chalk.yellow('\n💡 提示: Cookie可能已过期，请重新设置'));
          console.log(chalk.cyan('  cloudsaver-cli config --set-cookie'));
        }

        process.exit(1);
      }
    });
}
