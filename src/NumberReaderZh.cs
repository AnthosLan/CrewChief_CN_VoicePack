using CrewChiefV4.Audio;
using System;
using System.Collections.Generic;

namespace CrewChiefV4.NumberProcessing
{
    /**
     * Mandarin Chinese number reader.
     *
     * Chinese numbers are strictly positional and every digit keeps its own pronunciation, so almost
     * everything can be composed from 100 recordings (0-99) plus a handful of place-value words. That is
     * why this implementation needs ~134 sound folders where the English pack needs 1052 - there are no
     * "twenty-one" style fused forms to record, and no gendered variants like the Portuguese reader.
     *
     * The short-form methods (GetSecondsWithTenths, GetSeconds, GetSecondsWithHundredths,
     * GetMinutesAndSecondsWithFraction) are never reached: NumberReader.ConvertTimeToSounds gates them on
     * getLocale() being "en" or "it". Chinese therefore always takes the four-part
     * hours/minutes/seconds/tenths path, which caps spoken precision at tenths. Raising that to hundredths
     * would mean relaxing the locale check in the base class - see docs/数字与时间朗读设计.md.
     */
    public class NumberReaderZh : NumberReader
    {
        // folderPoint ("numbers/point"), folderMinute ("numbers/minute") and folderOh ("numbers/oh")
        // come from the base class.
        private static String folderNumbersStub = "numbers/";

        private static String folderHundred = folderNumbersStub + "hundred";            // 百
        private static String folderThousand = folderNumbersStub + "thousand";          // 千
        private static String folderTenThousand = folderNumbersStub + "ten_thousand";   // 万 - no English equivalent
        private static String folderLiang = folderNumbersStub + "liang";                // 两
        private static String folderMinus = folderNumbersStub + "minus";                // 负

        private static String folderHours = folderNumbersStub + "hours";                // 小时
        private static String folderMinutes = folderNumbersStub + "minutes";            // 分钟
        private static String folderSeconds = folderNumbersStub + "seconds";            // 秒

        protected override String getLocale()
        {
            return "zh";
        }

        /**
         * 小时。中文不分单复数，hour / hours 录同一个词，这里只用 hours。
         */
        protected override List<String> GetHoursSounds(int hours, int minutes, int seconds, int tenths,
            Boolean messageHasContentAfterTime, Precision precision)
        {
            List<String> messages = new List<String>();
            if (hours > 0)
            {
                messages.AddRange(countWithUnit(hours, folderHours));
            }
            return messages;
        }

        /**
         * 分。两种量词：后面还要读秒时用"分"（一分二十三秒四），否则用"分钟"（还剩十五分钟）。
         * 这跟英文实现相反 - 英文在有秒数时省略 "minutes"，中文必须保留，否则 "一二十三" 无法解析。
         */
        protected override List<String> GetMinutesSounds(int hours, int minutes, int seconds, int tenths,
            Boolean messageHasContentAfterTime, Precision precision)
        {
            List<String> messages = new List<String>();
            if (minutes > 0)
            {
                Boolean secondsFollow = hours == 0 && precision != Precision.MINUTES && (seconds > 0 || tenths > 0);
                messages.AddRange(countWithUnit(minutes, secondsFollow ? folderMinute : folderMinutes));
            }
            return messages;
        }

        /**
         * 秒。中文总是把"秒"读出来（英文在有分数时省略），小数位由 GetTenthsSounds 接在后面：
         * "二十三秒四"。
         */
        protected override List<String> GetSecondsSounds(int hours, int minutes, int seconds, int tenths,
            Boolean messageHasContentAfterTime, Precision precision)
        {
            List<String> messages = new List<String>();
            // 有小时数时秒不重要，和英文实现保持一致
            if (hours > 0 || precision == Precision.MINUTES)
            {
                return messages;
            }
            Boolean tenthsFollow = tenths > 0 && precision != Precision.SECONDS;
            if (minutes > 0 && seconds == 0 && tenthsFollow)
            {
                // 整分带小数，"一分零秒五"
                messages.Add(folderNumbersStub + "0");
                messages.Add(folderSeconds);
            }
            else if (seconds > 0)
            {
                if (minutes > 0 && seconds < 10)
                {
                    // 分之后的个位秒必须读出前导零，"一分零三秒"。01-09 是独立录音，
                    // 拼 "零" + "三" 会听成两个数。
                    messages.Add(folderNumbersStub + "0" + seconds);
                    messages.Add(folderSeconds);
                }
                else
                {
                    messages.AddRange(countWithUnit(seconds, folderSeconds));
                }
            }
            return messages;
        }

        /**
         * 十分位。有整数部分时"秒"已经读过了，这里只补小数位（二十三秒四）；没有整数部分时
         * 读完整的"零点三秒" - 中文口语不说"三个十分之一"，所以 tenth / tenths 文件夹用不上。
         */
        protected override List<String> GetTenthsSounds(int hours, int minutes, int seconds, int tenths,
            Boolean messageHasContentAfterTime, Precision precision)
        {
            List<String> messages = new List<String>();
            if (hours > 0 || tenths <= 0 || tenths >= 10
                || precision == Precision.SECONDS || precision == Precision.MINUTES)
            {
                return messages;
            }
            if (minutes == 0 && seconds == 0)
            {
                messages.Add(folderNumbersStub + "0");
                messages.Add(folderPoint);
                messages.Add(folderNumbersStub + tenths);
                messages.Add(folderSeconds);
            }
            else
            {
                messages.Add(folderNumbersStub + tenths);
            }
            return messages;
        }

        /**
         * 整数 -99999 到 99999。
         * allowShortHundredsForThisNumber 对中文无意义 - 没有 "one oh four" 这种读法，115 只能读
         * "一百一十五"。
         */
        protected override List<String> GetIntegerSounds(char[] digits, Boolean allowShortHundredsForThisNumber,
            Boolean messageHasContentAfterNumber, ARTICLE_GENDER gender = ARTICLE_GENDER.NA)
        {
            List<String> messages = new List<String>();
            String digitsString = new String(digits);
            Boolean negative = digitsString.StartsWith("-");
            if (negative)
            {
                digitsString = digitsString.Substring(1);
            }
            int number;
            if (!int.TryParse(digitsString, out number))
            {
                Console.WriteLine("Unable to read number " + digitsString);
                return messages;
            }
            if (negative)
            {
                messages.Add(folderMinus);
            }
            messages.AddRange(readWholeNumber(number, false));
            return messages;
        }

        /**
         * 中文读数的核心：万 / 千 / 百 逐级拆分，每级不足下一级时补"零"。
         *   1005 -> 一千零五      1050 -> 一千零五十      1500 -> 一千五百
         *   305  -> 三百零五      345  -> 三百四十五      10500 -> 一万零五百
         * hasHigherPlace 传给 readUnder100 处理"十"的读法差异。
         */
        private List<String> readWholeNumber(int n, Boolean hasHigherPlace)
        {
            List<String> sounds = new List<String>();
            if (n == 0)
            {
                sounds.Add(folderNumbersStub + "0");
                return sounds;
            }
            if (n >= 10000)
            {
                int remainder = n % 10000;
                sounds.AddRange(countWithUnit(n / 10000, folderTenThousand));
                if (remainder > 0)
                {
                    // 万位后不足千要补"零"：一万零五百
                    if (remainder < 1000)
                    {
                        sounds.Add(folderOh);
                    }
                    sounds.AddRange(readWholeNumber(remainder, true));
                }
                return sounds;
            }
            if (n >= 1000)
            {
                int remainder = n % 1000;
                sounds.AddRange(countWithUnit(n / 1000, folderThousand));
                if (remainder > 0)
                {
                    if (remainder < 100)
                    {
                        sounds.Add(folderOh);
                    }
                    sounds.AddRange(readWholeNumber(remainder, true));
                }
                return sounds;
            }
            if (n >= 100)
            {
                int remainder = n % 100;
                // 百位的 2 读"二百"，不是"两百" - 跟千 / 万不同，所以不走 countWithUnit
                sounds.Add(folderNumbersStub + (n / 100));
                sounds.Add(folderHundred);
                if (remainder > 0)
                {
                    if (remainder < 10)
                    {
                        sounds.Add(folderOh);
                    }
                    sounds.AddRange(readUnder100(remainder, true));
                }
                return sounds;
            }
            return readUnder100(n, hasHigherPlace);
        }

        /**
         * 0-99 全部是独立录音，直接取。唯一的例外是 10-19：单独读是"十五"，跟在更高位后面要读成
         * "一十五"（一百一十五），所以补一个"一"。
         */
        private List<String> readUnder100(int n, Boolean hasHigherPlace)
        {
            List<String> sounds = new List<String>();
            if (hasHigherPlace && n >= 10 && n < 20)
            {
                sounds.Add(folderNumbersStub + "1");
            }
            sounds.Add(folderNumbersStub + n);
            return sounds;
        }

        /**
         * 数量 + 量词。两件事：
         *   - 跟量词的 2 读"两"（两秒 / 两分钟 / 两千），只有百位和 20-99 里的 2 读"二"
         *   - 优先用整段录音（numbers/1_seconds = "一秒"）。"一"在量词前有变调，单字录音拼出来是
         *     孤立调值。这些文件夹缺失时自动退回拼接，所以纯属可选优化。
         */
        private List<String> countWithUnit(int count, String unitFolder)
        {
            List<String> sounds = new List<String>();
            String combined = folderNumbersStub + count + "_" + unitFolder.Substring(folderNumbersStub.Length);
            if (SoundCache.availableSounds.Contains(combined))
            {
                sounds.Add(combined);
                return sounds;
            }
            if (count == 2)
            {
                sounds.Add(folderLiang);
            }
            else
            {
                sounds.AddRange(readWholeNumber(count, false));
            }
            sounds.Add(unitFolder);
            return sounds;
        }

        /**
         * 钟点（几点几分），给 CommonActions.reportCurrentTime() 用。
         *
         * 不是 NumberReader 的抽象方法——基类只管时长（"一分二十三秒四"），钟点是另一回事，
         * 而英文那条路把片段按 hour + oh + minute + am/pm 拼，是英文语序。中文有两处不同：
         *
         *   1. 上午/下午在最前面，不在最后
         *   2. 小时后面跟「点」。「八小时零五分」是时长，不是钟点
         *
         * 放在这里而不是 CommonActions，是为了共用 countWithUnit 的量词规则——2 点要读「两点」，
         * 和「两圈」「两秒」同一条规则，不该在调用方再实现一遍。
         *
         * 「点」复用 numbers/point：钟点的点和小数点的点是同一个字、同一段录音。
         *
         * hour 传 24 小时制。
         */
        public List<String> GetTimeOfDaySounds(int hour, int minute, String folderAM, String folderPM)
        {
            List<String> sounds = new List<String>();
            sounds.Add(hour >= 12 ? folderPM : folderAM);

            int hour12 = hour % 12;
            if (hour12 == 0)
            {
                // 0 点和 12 点都读「十二点」，靠前面的上午/下午区分，与英文包一致。
                hour12 = 12;
            }
            sounds.AddRange(countWithUnit(hour12, folderPoint));

            if (minute > 0)
            {
                if (minute < 10)
                {
                    // 八点零五，不是八点五。
                    sounds.Add(folderOh);
                }
                sounds.AddRange(readWholeNumber(minute, false));
                sounds.Add(folderMinute);
            }
            return sounds;
        }

        // The remaining methods are English / Italian short-form optimisations. ConvertTimeToSounds only
        // calls them when getLocale() is "en" or "it", so they are unreachable here. They return empty
        // rather than null because the base class AddRange()s the results.

        protected override String GetSecondsWithTenths(int seconds, int tenths)
        {
            return null;
        }

        protected override List<String> GetSeconds(int seconds)
        {
            return new List<String>();
        }

        protected override List<String> GetSecondsWithHundredths(int seconds, int hundredths)
        {
            return new List<String>();
        }

        protected override List<String> GetMinutesAndSecondsWithFraction(int minutes, int seconds, String fraction,
            Boolean messageHasContentAfterTime)
        {
            return new List<String>();
        }
    }
}
