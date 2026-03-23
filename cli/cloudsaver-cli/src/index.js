#!/usr/bin/env node

import chalk from 'chalk';
import { Command } from 'commander';
import { configCommand } from './commands/config.js';
import { saveCommand } from './commands/save.js';
import { searchCommand } from './commands/search.js';

const program = new Command();

program
  .name('cloudsaver-cli')
  .description('CloudSaver CLI - 网盘资源搜索与115转存工具')
  .version('1.0.0')
  .usage('<command> [options]')
  .addHelpCommand('help [command]', '显示帮助信息')
  .helpOption('-h, --help', '显示帮助信息');

searchCommand(program);
saveCommand(program);
configCommand(program);

async function main() {
  if (process.argv.length === 2) {
    console.log(chalk.cyan.bold('\n☁️  CloudSaver CLI\n'));
    console.log(chalk.gray('网盘资源搜索与115转存工具\n'));
    program.outputHelp();
    process.exit(0);
  }

  program.exitOverride();

  try {
    await program.parseAsync(process.argv);
  } catch (error) {
    if (!['commander.help', 'commander.helpDisplayed', 'commander.version'].includes(error.code)) {
      console.error(chalk.red('错误:'), error.message);
      process.exit(1);
    }
  }
}

main();
