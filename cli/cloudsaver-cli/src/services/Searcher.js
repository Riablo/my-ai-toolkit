import * as cheerio from 'cheerio';
import { createTelegramAxios } from '../utils/axiosInstance.js';

export class Searcher {
  constructor() {
    this.api = createTelegramAxios();
    this.cloudPatterns = {
      pan115: /https?:\/\/(?:115|anxia|115cdn)\.com\/s\/[^\s<>"]+/g,
      aliyun: /https?:\/\/\w+\.(?:alipan|aliyundrive)\.com\/[^\s<>"]+/g,
      quark: /https?:\/\/pan\.quark\.cn\/[^\s<>"]+/g,
      baidu: /https?:\/\/(?:pan|yun)\.baidu\.com\/[^\s<>"]+/g,
      tianyi: /https?:\/\/cloud\.189\.cn\/[^\s<>"]+/g,
      pan123: /https?:\/\/(?:www\.)?123[^/\s<>"]+\.com\/s\/[^\s<>"]+/g,
    };
    this.clarityRules = [
      { score: 900, patterns: [/\b8K\b/i, /\b4320P\b/i, /FUHD/i] },
      { score: 800, patterns: [/\b4K\b/i, /\b2160P\b/i, /\bUHD\b/i] },
      { score: 700, patterns: [/\b1440P\b/i, /\b2K\b/i] },
      { score: 600, patterns: [/\b1080P\b/i, /\b1080I\b/i, /\bFHD\b/i] },
      { score: 500, patterns: [/\b720P\b/i] },
      { score: 400, patterns: [/\b540P\b/i] },
      { score: 300, patterns: [/\b480P\b/i, /\bSD\b/i] },
      { score: 200, patterns: [/\b360P\b/i] },
    ];
    this.clarityBoostRules = [
      { score: 40, patterns: [/蓝光原盘/i, /BluRay/i, /REMUX/i] },
      { score: 30, patterns: [/\bWEB-DL\b/i, /\bWEBRip\b/i] },
      { score: 20, patterns: [/\bHDR\b/i, /杜比视界/i, /\bDV\b/i] },
      { score: -50, patterns: [/\bCAM\b/i, /\bTS\b/i, /枪版/i] },
    ];
  }

  extractCloudLinks(text) {
    const links = [];

    Object.entries(this.cloudPatterns).forEach(([type, pattern]) => {
      const matches = text.match(pattern);
      if (matches) {
        matches.forEach((url) => {
          links.push({ url, type });
        });
      }
    });

    const unique = new Map();
    links.forEach((link) => unique.set(link.url, link));
    return Array.from(unique.values());
  }

  getCloudTypePriority(type) {
    const priority = {
      pan115: 1,
      aliyun: 2,
      quark: 3,
      baidu: 4,
      tianyi: 5,
      pan123: 6,
      unknown: 7,
    };
    return priority[type] || 7;
  }

  getResultCloudPriority(result) {
    return result.cloudLinks.reduce(
      (bestPriority, link) => Math.min(bestPriority, this.getCloudTypePriority(link.type)),
      Number.POSITIVE_INFINITY,
    );
  }

  getClarityScore(result) {
    const text = [
      result.title,
      result.content,
      ...(result.tags || []),
    ]
      .filter(Boolean)
      .join(' ');

    let score = 0;

    for (const rule of this.clarityRules) {
      if (rule.patterns.some((pattern) => pattern.test(text))) {
        score = rule.score;
        break;
      }
    }

    for (const rule of this.clarityBoostRules) {
      if (rule.patterns.some((pattern) => pattern.test(text))) {
        score += rule.score;
      }
    }

    return score;
  }

  compareResults(left, right) {
    const cloudPriorityDiff = this.getResultCloudPriority(left) - this.getResultCloudPriority(right);
    if (cloudPriorityDiff !== 0) {
      return cloudPriorityDiff;
    }

    const clarityDiff = this.getClarityScore(right) - this.getClarityScore(left);
    if (clarityDiff !== 0) {
      return clarityDiff;
    }

    return new Date(right.pubDate) - new Date(left.pubDate);
  }

  async searchChannel(channel, keyword) {
    try {
      const url = keyword
        ? `/${channel.id}?q=${encodeURIComponent(keyword)}`
        : `/${channel.id}`;

      const response = await this.api.get(url);
      const html = response.data;
      const $ = cheerio.load(html);
      const results = [];

      $('.tgme_widget_message_wrap').each((_, element) => {
        const messageEl = $(element);

        const messageId = messageEl
          .find('.tgme_widget_message')
          .data('post')
          ?.toString()
          .split('/')[1] || '';

        const title = messageEl
          .find('.js-message_text')
          .html()
          ?.split('<br>')[0]
          .replace(/\u003c[^\u003e]+\u003e/g, '')
          .replace(/\n/g, '')
          .trim() || '';

        const content = messageEl
          .find('.js-message_text')
          .text()
          .replace(title, '')
          .trim() || '';

        const pubDate = messageEl.find('time').attr('datetime') || '';

        const image = messageEl
          .find('.tgme_widget_message_photo_wrap')
          .attr('style')
          ?.match(/url\('(.+?)'\)/)?.[1];

        const tags = [];
        messageEl.find('.tgme_widget_message_text a').each((__, tagElement) => {
          const tagText = $(tagElement).text();
          if (tagText && tagText.startsWith('#')) {
            tags.push(tagText);
          }
        });

        const allText = messageEl.find('.tgme_widget_message_text').html() || '';
        const cloudLinks = this.extractCloudLinks(allText);

        if (cloudLinks.length > 0) {
          cloudLinks.sort(
            (left, right) => this.getCloudTypePriority(left.type) - this.getCloudTypePriority(right.type),
          );

          results.push({
            messageId,
            title: title || '无标题',
            content,
            pubDate,
            image,
            cloudLinks,
            tags,
            channel: channel.name,
            channelId: channel.id,
          });
        }
      });

      return results.reverse();
    } catch (error) {
      console.error(`搜索频道 ${channel.name} 失败:`, error);
      return [];
    }
  }

  async searchAll(keyword, channels) {
    const allResults = [];

    for (const channel of channels) {
      const results = await this.searchChannel(channel, keyword);
      allResults.push(...results);
    }

    return allResults.sort((left, right) => this.compareResults(left, right));
  }
}
